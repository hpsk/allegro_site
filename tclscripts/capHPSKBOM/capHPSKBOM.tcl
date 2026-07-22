#/////////////////////////////////////////////////////////////////////////////////
#  TCL file: capHPSKBOM.tcl
#            HPSK_BOM - Customizable Bill of Materials exporter for OrCAD Capture
#
#  Menu    : Tools > HPSK_BOM  (registered by capAutoLoad/capHPSKBOMInit.tcl)
#  Storage : %HOME%\HPSK_BOM.JSON (falls back to %USERPROFILE% when HOME is unset)
#
#  See HPSK_BOM.md for the user guide and HPSK_BOM_CCR.md for version history.
#/////////////////////////////////////////////////////////////////////////////////

package provide capHPSKBOM 1.0

package require capAppUtils 1.0

namespace eval ::HPSKBOM {
    # keep in sync with the latest entry in HPSK_BOM_CCR.md
    variable mVersionString "ver. 1.0.8 (by 행복찾기)"

    # ---- Capture handles -----------------------------------------------------
    variable mForm            ""
    variable mPresetCombo     ""
    variable mFieldsInner     ""
    variable mPreviewText     ""
    variable mHeaderText      ""

    # field names that never appear as a selectable BOM field - they only
    # feed the physical-part de-duplication logic (see CollapsePhysicalParts)
    variable mHiddenFieldNames {"Part Reference" "Designator"}

    # ---- Design data (rebuilt every time the dialog is opened) --------------
    variable mFields          [list]     ;# ordered list of dicts: field / bomName / include
    variable mParts           [list]     ;# list of dicts: ref / props (one per placed instance)
    variable mPhysicalParts   [list]     ;# mParts after collapsing multi-gate/section duplicates

    # per-row live UI state, keyed by field name
    variable mIncludeVars
    variable mBomNameVars
    array set mIncludeVars {}
    array set mBomNameVars {}

    # ---- Export settings (live UI state) -------------------------------------
    variable mDelimiter          ","
    variable mFormat             "CSV"
    variable mHeaderTemplate     ""
    variable mHeaderIsPlaceholder 1
    variable mOutputFile         ""

    # ---- Persisted presets ----------------------------------------------------
    variable mPresetsData     [dict create]
    variable mLastPreset      "Default"
}

#/////////////////////////////////////////////////////////////////////////////////
# Small pure-TCL JSON reader/writer (kept local, no external package dependency)
#/////////////////////////////////////////////////////////////////////////////////

proc ::HPSKBOM::JsonQuote {pText} {
    set lText [string map [list \\ \\\\ \" \\\" \n \\n \r \\r \t \\t] $pText]
    return "\"$lText\""
}

proc ::HPSKBOM::JsonSkipWs {sVar iVar} {
    upvar 1 $sVar s
    upvar 1 $iVar i
    set n [string length $s]
    while {$i < $n} {
        set c [string index $s $i]
        if {$c eq " " || $c eq "\t" || $c eq "\n" || $c eq "\r"} {
            incr i
        } else {
            break
        }
    }
}

proc ::HPSKBOM::JsonParseString {sVar iVar} {
    upvar 1 $sVar s
    upvar 1 $iVar i
    incr i
    set lOut ""
    set n [string length $s]
    while {$i < $n} {
        set c [string index $s $i]
        if {$c eq "\""} { incr i; break }
        if {$c eq "\\"} {
            incr i
            set e [string index $s $i]
            switch -- $e {
                n { append lOut "\n" }
                t { append lOut "\t" }
                r { append lOut "\r" }
                b { append lOut "\b" }
                f { append lOut "\f" }
                "\"" { append lOut "\"" }
                "\\" { append lOut "\\" }
                "/" { append lOut "/" }
                u {
                    set lHex [string range $s [expr {$i+1}] [expr {$i+4}]]
                    incr i 4
                    scan $lHex "%x" lCode
                    append lOut [format %c $lCode]
                }
                default { append lOut $e }
            }
            incr i
        } else {
            append lOut $c
            incr i
        }
    }
    return $lOut
}

proc ::HPSKBOM::JsonParseValue {sVar iVar} {
    upvar 1 $sVar s
    upvar 1 $iVar i
    JsonSkipWs s i
    set c [string index $s $i]
    if {$c eq "\{"} { return [JsonParseObject s i] }
    if {$c eq "\["} { return [JsonParseArray s i] }
    if {$c eq "\""} { return [JsonParseString s i] }
    if {[string range $s $i [expr {$i+3}]] eq "true"}  { incr i 4; return 1 }
    if {[string range $s $i [expr {$i+4}]] eq "false"} { incr i 5; return 0 }
    if {[string range $s $i [expr {$i+3}]] eq "null"}  { incr i 4; return "" }
    set lStart $i
    set n [string length $s]
    while {$i < $n} {
        set c2 [string index $s $i]
        if {[string is digit $c2] || $c2 eq "-" || $c2 eq "+" || $c2 eq "." || $c2 eq "e" || $c2 eq "E"} {
            incr i
        } else {
            break
        }
    }
    return [string range $s $lStart [expr {$i-1}]]
}

proc ::HPSKBOM::JsonParseArray {sVar iVar} {
    upvar 1 $sVar s
    upvar 1 $iVar i
    incr i
    set lList [list]
    JsonSkipWs s i
    if {[string index $s $i] eq "\]"} { incr i; return $lList }
    while {1} {
        set lVal [JsonParseValue s i]
        lappend lList $lVal
        JsonSkipWs s i
        set c [string index $s $i]
        if {$c eq ","} { incr i; JsonSkipWs s i; continue }
        if {$c eq "\]"} { incr i; break }
        error "HPSK_BOM: malformed JSON array near position $i"
    }
    return $lList
}

proc ::HPSKBOM::JsonParseObject {sVar iVar} {
    upvar 1 $sVar s
    upvar 1 $iVar i
    incr i
    set lDict [dict create]
    JsonSkipWs s i
    if {[string index $s $i] eq "\}"} { incr i; return $lDict }
    while {1} {
        JsonSkipWs s i
        set lKey [JsonParseString s i]
        JsonSkipWs s i
        if {[string index $s $i] ne ":"} { error "HPSK_BOM: expected ':' near position $i" }
        incr i
        JsonSkipWs s i
        set lVal [JsonParseValue s i]
        dict set lDict $lKey $lVal
        JsonSkipWs s i
        set c [string index $s $i]
        if {$c eq ","} { incr i; continue }
        if {$c eq "\}"} { incr i; break }
        error "HPSK_BOM: expected ',' or closing brace near position $i"
    }
    return $lDict
}

proc ::HPSKBOM::JsonParse {pText} {
    set s $pText
    set i 0
    JsonSkipWs s i
    return [JsonParseValue s i]
}

#/////////////////////////////////////////////////////////////////////////////////
# Persistence : %HOME%\HPSK_BOM.JSON
#/////////////////////////////////////////////////////////////////////////////////

proc ::HPSKBOM::HomeDir {} {
    if {[info exists ::env(HOME)] && $::env(HOME) ne ""} {
        return $::env(HOME)
    }
    if {[info exists ::env(USERPROFILE)] && $::env(USERPROFILE) ne ""} {
        return $::env(USERPROFILE)
    }
    return [pwd]
}

proc ::HPSKBOM::JsonFilePath {} {
    return [file join [::HPSKBOM::HomeDir] "HPSK_BOM.JSON"]
}

proc ::HPSKBOM::StoreToJsonText {} {
    variable mPresetsData
    variable mLastPreset

    set lNames [lsort -dictionary [dict keys $mPresetsData]]
    set lBuf "\{\n"
    append lBuf "  \"version\": 1,\n"
    append lBuf "  \"lastPreset\": [::HPSKBOM::JsonQuote $mLastPreset],\n"
    append lBuf "  \"presets\": \{\n"

    set lPresetEntries [list]
    foreach lName $lNames {
        set lPreset [dict get $mPresetsData $lName]

        set lFieldEntries [list]
        foreach lF [dict get $lPreset fields] {
            lappend lFieldEntries [format "      \{ \"field\": %s, \"bomName\": %s, \"include\": %d \}" \
                [::HPSKBOM::JsonQuote [dict get $lF field]] \
                [::HPSKBOM::JsonQuote [dict get $lF bomName]] \
                [expr {[dict get $lF include] ? 1 : 0}]]
        }
        set lFieldsJson "\[\n[join $lFieldEntries ",\n"]\n    \]"

        lappend lPresetEntries [format "    %s: \{\n      \"delimiter\": %s,\n      \"format\": %s,\n      \"headerTemplate\": %s,\n      \"fields\": %s\n    \}" \
            [::HPSKBOM::JsonQuote $lName] \
            [::HPSKBOM::JsonQuote [dict get $lPreset delimiter]] \
            [::HPSKBOM::JsonQuote [dict get $lPreset format]] \
            [::HPSKBOM::JsonQuote [dict get $lPreset headerTemplate]] \
            $lFieldsJson]
    }
    append lBuf [join $lPresetEntries ",\n"]
    append lBuf "\n  \}\n\}\n"
    return $lBuf
}

proc ::HPSKBOM::LoadStore {} {
    variable mPresetsData
    variable mLastPreset

    set mPresetsData [dict create]
    set mLastPreset "Default"

    set lPath [::HPSKBOM::JsonFilePath]
    if {![file exists $lPath]} { return }

    if {[catch {
        set lFh [open $lPath r]
        fconfigure $lFh -encoding utf-8
        set lText [read $lFh]
        close $lFh

        set lRoot [::HPSKBOM::JsonParse $lText]

        if {[dict exists $lRoot lastPreset]} {
            set mLastPreset [dict get $lRoot lastPreset]
        }

        if {[dict exists $lRoot presets]} {
            set lPresetsRoot [dict get $lRoot presets]
            foreach lName [dict keys $lPresetsRoot] {
                set lRaw [dict get $lPresetsRoot $lName]

                set lFields [list]
                if {[dict exists $lRaw fields]} {
                    foreach lF [dict get $lRaw fields] {
                        set lFieldName ""
                        set lBomName   ""
                        set lInclude   0
                        catch {set lFieldName [dict get $lF field]}
                        catch {set lBomName   [dict get $lF bomName]}
                        catch {set lInclude   [dict get $lF include]}
                        if {$lBomName eq ""} { set lBomName $lFieldName }
                        lappend lFields [dict create field $lFieldName bomName $lBomName include $lInclude]
                    }
                }

                set lDelim         ","
                set lFormat        "CSV"
                set lHeaderTemplate ""
                catch {set lDelim         [dict get $lRaw delimiter]}
                catch {set lFormat        [dict get $lRaw format]}
                # v1.0.x used a boolean "header" flag; v1.0.4+ uses a free-text
                # "headerTemplate" instead. There is no meaningful way to
                # convert the old flag, so old presets simply start with an
                # empty (placeholder-hint) template.
                catch {set lHeaderTemplate [dict get $lRaw headerTemplate]}

                dict set mPresetsData $lName [dict create \
                    delimiter $lDelim format $lFormat headerTemplate $lHeaderTemplate \
                    fields $lFields]
            }
        }
    } lErr]} {
        catch {capAppUtils::showError "HPSK_BOM" "설정 파일을 읽는 중 오류가 발생했습니다:\n$lPath\n\n$lErr"}
    }
}

proc ::HPSKBOM::SaveStore {} {
    set lPath [::HPSKBOM::JsonFilePath]
    if {[catch {
        set lText [::HPSKBOM::StoreToJsonText]
        set lFh [open $lPath w]
        fconfigure $lFh -encoding utf-8
        puts -nonewline $lFh $lText
        close $lFh
    } lErr]} {
        capAppUtils::showError "HPSK_BOM" "설정 파일을 저장하는 중 오류가 발생했습니다:\n$lPath\n\n$lErr"
        return 0
    }
    return 1
}

#/////////////////////////////////////////////////////////////////////////////////
# Design scan : walk the active design's occurrence tree and collect
# every part instance's Reference + effective properties (built-in + user).
#/////////////////////////////////////////////////////////////////////////////////

proc ::HPSKBOM::GetReference {pInstOcc} {
    set lName [DboTclHelper_sMakeCString]
    set lStatus [$pInstOcc GetReference $lName]
    set lRef [DboTclHelper_sGetConstCharPtr $lName]
    $lStatus -delete
    return $lRef
}

proc ::HPSKBOM::ReadEffectiveProps {pInstOcc pFieldOrderVar pFieldSeenVar} {
    upvar 1 $pFieldOrderVar lFieldOrder
    upvar 1 $pFieldSeenVar  lFieldSeen

    set lStatus     [DboState]
    set lPropsIter  [$pInstOcc NewEffectivePropsIter $lStatus]
    set lPrpName    [DboTclHelper_sMakeCString]
    set lPrpValue   [DboTclHelper_sMakeCString]
    set lPrpType    [DboTclHelper_sMakeDboValueType]
    set lEditable   [DboTclHelper_sMakeInt]

    set lProps [dict create]

    set lIterStatus [$lPropsIter NextEffectiveProp $lPrpName $lPrpValue $lPrpType $lEditable]
    while {[$lIterStatus OK] == 1} {
        set lPName  [DboTclHelper_sGetConstCharPtr $lPrpName]
        set lPValue [DboTclHelper_sGetConstCharPtr $lPrpValue]
        dict set lProps $lPName $lPValue
        if {![dict exists $lFieldSeen $lPName]} {
            dict set lFieldSeen $lPName 1
            lappend lFieldOrder $lPName
        }
        set lIterStatus [$lPropsIter NextEffectiveProp $lPrpName $lPrpValue $lPrpType $lEditable]
    }
    delete_DboEffectivePropsIter $lPropsIter
    $lStatus -delete
    return $lProps
}

proc ::HPSKBOM::WalkOccurrence {pInstOcc pFieldOrderVar pFieldSeenVar} {
    upvar 1 $pFieldOrderVar lFieldOrder
    upvar 1 $pFieldSeenVar  lFieldSeen
    variable mParts

    set lStatus  [DboState]
    set lNullObj NULL

    set lInstOccIter [$pInstOcc NewChildrenIter $lStatus $::IterDefs_INSTS]
    $lInstOccIter Sort $lStatus
    set lChildOcc [$lInstOccIter NextOccurrence $lStatus]
    while {$lChildOcc != $lNullObj} {
        set lChildInstOcc [DboOccurrenceToDboInstOccurrence $lChildOcc]

        set lIsPrimitive [$lChildInstOcc IsPrimitive $lStatus]
        if {$lIsPrimitive == 1} {
            set lRef   [::HPSKBOM::GetReference $lChildInstOcc]
            set lProps [::HPSKBOM::ReadEffectiveProps $lChildInstOcc lFieldOrder lFieldSeen]
            dict set lProps "Reference" $lRef
            lappend mParts [dict create ref $lRef props $lProps]
        }

        ::HPSKBOM::WalkOccurrence $lChildInstOcc lFieldOrder lFieldSeen

        set lChildOcc [$lInstOccIter NextOccurrence $lStatus]
    }
    delete_DboOccurrenceChildrenIter $lInstOccIter
    $lStatus -delete
}

proc ::HPSKBOM::IsLockedField {pFieldName} {
    # "Reference" always ships in the BOM and can be reordered but never
    # unchecked - it is the only column combined by GroupPartsForExport.
    return [expr {$pFieldName eq "Reference"}]
}

proc ::HPSKBOM::GetSectionDesignator {pProps} {
    # OrCAD's "Part Reference" carries the per-gate/section suffix (e.g.
    # "U1A", "U1B") for a multi-section physical part. Some designs instead
    # (or additionally) use a "Designator" property for the same purpose -
    # both are honored, "Part Reference" taking priority.
    set lVal ""
    catch {set lVal [dict get $pProps "Part Reference"]}
    if {[string trim $lVal] eq ""} {
        catch {set lVal [dict get $pProps "Designator"]}
    }
    return [string trim $lVal]
}

proc ::HPSKBOM::GetImplementation {pProps} {
    set lVal ""
    catch {set lVal [dict get $pProps "Implementation"]}
    return $lVal
}

# Multi-gate/multi-section ICs place one instance per gate, all sharing the
# same Reference (e.g. "U1") but with different Part Reference/Designator
# ("U1A", "U1B", ...) - that is still a single physical part and must be
# counted once. Two (or more) instances collapse into one physical part
# when they share the same Reference AND the same Implementation AND every
# one of them has a non-empty Part Reference/Designator. If any instance in
# that Reference+Implementation group has no designator, or a different
# Implementation appears under the same Reference, they are kept as
# separate physical parts (see HPSK_BOM.md "설계 결정").
proc ::HPSKBOM::CollapsePhysicalParts {pParts} {
    set lPartitionOrder [list]
    set lPartitions     [dict create]

    foreach lPart $pParts {
        set lRef  [dict get $lPart ref]
        set lImpl [::HPSKBOM::GetImplementation [dict get $lPart props]]
        set lKey  [list $lRef $lImpl]

        if {![dict exists $lPartitions $lKey]} {
            dict set lPartitions $lKey [list]
            lappend lPartitionOrder $lKey
        }
        dict set lPartitions $lKey [linsert [dict get $lPartitions $lKey] end $lPart]
    }

    set lOut [list]
    foreach lKey $lPartitionOrder {
        set lItems [dict get $lPartitions $lKey]

        set lAllHaveDesignator 1
        foreach lItem $lItems {
            if {[::HPSKBOM::GetSectionDesignator [dict get $lItem props]] eq ""} {
                set lAllHaveDesignator 0
                break
            }
        }

        if {[llength $lItems] > 1 && $lAllHaveDesignator} {
            lappend lOut [lindex $lItems 0]
        } else {
            foreach lItem $lItems { lappend lOut $lItem }
        }
    }
    return $lOut
}

proc ::HPSKBOM::ScanDesign {} {
    variable mFields
    variable mParts
    variable mPhysicalParts
    variable mHiddenFieldNames

    set mParts        [list]
    set mFields       [list]
    set mPhysicalParts [list]

    if {[catch {GetActivePMDesign} lDesign]} { return 0 }
    if {$lDesign eq "" || $lDesign eq "NULL" || $lDesign == 1} { return 0 }

    set lStatus  [DboState]
    set lRootOcc [$lDesign GetRootOccurrence $lStatus]
    $lStatus -delete

    if {$lRootOcc eq "" || $lRootOcc eq "NULL"} { return 0 }

    set lFieldOrder [list "Reference"]
    set lFieldSeen  [dict create "Reference" 1]

    ::HPSKBOM::WalkOccurrence $lRootOcc lFieldOrder lFieldSeen

    foreach lName $lFieldOrder {
        if {[lsearch -exact $mHiddenFieldNames $lName] >= 0} { continue }
        lappend mFields [dict create field $lName bomName $lName include 1]
    }

    set mPhysicalParts [::HPSKBOM::CollapsePhysicalParts $mParts]
    return 1
}

#/////////////////////////////////////////////////////////////////////////////////
# BOM text generation (shared by the preview pane and the real export)
#/////////////////////////////////////////////////////////////////////////////////

proc ::HPSKBOM::CollectActiveFields {} {
    variable mFields
    variable mIncludeVars
    variable mBomNameVars

    set lOut [list]
    foreach lF $mFields {
        set lFieldName [dict get $lF field]
        set lInclude   [dict get $lF include]
        set lBomName   [dict get $lF bomName]
        catch {set lInclude $mIncludeVars($lFieldName)}
        catch {set lBomName $mBomNameVars($lFieldName)}
        if {[::HPSKBOM::IsLockedField $lFieldName]} { set lInclude 1 }
        lappend lOut [dict create field $lFieldName bomName $lBomName include $lInclude]
    }
    return $lOut
}

# Rows are grouped by the tuple of *checked* field values (excluding
# "Reference", which is combined/counted separately below), mirroring how a
# real BOM combines identical parts. If nothing else is checked there is no
# basis for comparison, so every physical part stays on its own row instead
# of being lumped into one giant group (see HPSK_BOM.md "설계 결정").
proc ::HPSKBOM::GroupPartsForExport {pActiveFields} {
    variable mPhysicalParts

    set lCheckedFields [list]
    foreach lF $pActiveFields {
        if {[dict get $lF include] && [dict get $lF field] ne "Reference"} {
            lappend lCheckedFields $lF
        }
    }

    if {[llength $lCheckedFields] == 0} {
        set lRows [list]
        foreach lPart $mPhysicalParts {
            lappend lRows [dict create \
                reference [dict get $lPart ref] qty 1 valuesByField [dict create]]
        }
        return $lRows
    }

    set lGroups [dict create]
    set lOrder  [list]

    foreach lPart $mPhysicalParts {
        set lRef   [dict get $lPart ref]
        set lProps [dict get $lPart props]

        set lValuesByField [dict create]
        set lKeyParts [list]
        foreach lF $lCheckedFields {
            set lFieldName [dict get $lF field]
            set lVal ""
            catch {set lVal [dict get $lProps $lFieldName]}
            dict set lValuesByField $lFieldName $lVal
            lappend lKeyParts $lVal
        }
        set lKey [join $lKeyParts ""]

        if {[dict exists $lGroups $lKey]} {
            set lEntry [dict get $lGroups $lKey]
            dict lappend lEntry refs $lRef
            dict set lGroups $lKey $lEntry
        } else {
            dict set lGroups $lKey [dict create refs [list $lRef] valuesByField $lValuesByField]
            lappend lOrder $lKey
        }
    }

    set lRows [list]
    foreach lKey $lOrder {
        set lEntry [dict get $lGroups $lKey]
        set lRefs  [lsort -dictionary [dict get $lEntry refs]]
        lappend lRows [dict create \
            reference [join $lRefs ", "] \
            qty       [llength $lRefs] \
            valuesByField [dict get $lEntry valuesByField]]
    }
    return $lRows
}

proc ::HPSKBOM::HtmlEscape {pText} {
    # each entity is double-quoted so the embedded ";" is not parsed as a
    # command separator inside this [list ...] command substitution
    return [string map [list "&" "&amp;" "<" "&lt;" ">" "&gt;" "\"" "&quot;"] $pText]
}

proc ::HPSKBOM::JoinRow {pCells pDelim pQuote} {
    set lOut [list]
    foreach c $pCells {
        if {$pQuote} {
            set c [string map [list \" \"\"] $c]
            lappend lOut "\"$c\""
        } else {
            lappend lOut $c
        }
    }
    return [join $lOut $pDelim]
}

# Builds the ordered output columns from the active field list. "Reference"
# is a normal, reorderable entry in mFields/pActiveFields, but its cell
# comes from the row's combined "reference" string, not valuesByField.
# "Qty" is not a real field and always comes last.
proc ::HPSKBOM::BuildColumns {pActiveFields} {
    set lColumns [list]
    foreach lF $pActiveFields {
        if {![dict get $lF include]} { continue }
        set lFieldName [dict get $lF field]
        if {$lFieldName eq "Reference"} {
            lappend lColumns [dict create kind ref label [dict get $lF bomName]]
        } else {
            lappend lColumns [dict create kind field field $lFieldName label [dict get $lF bomName]]
        }
    }
    lappend lColumns [dict create kind qty label "Qty"]
    return $lColumns
}

proc ::HPSKBOM::RowCells {pRow pColumns} {
    set lCells [list]
    foreach lCol $pColumns {
        switch -- [dict get $lCol kind] {
            ref   { lappend lCells [dict get $pRow reference] }
            qty   { lappend lCells [dict get $pRow qty] }
            field {
                set lVal ""
                catch {set lVal [dict get $pRow valuesByField [dict get $lCol field]]}
                lappend lCells $lVal
            }
        }
    }
    return $lCells
}

# Bottom summary row: "Total" in the first column, the grand total quantity
# (summed across every row, not just a truncated preview slice) in the Qty
# column, everything else left blank.
proc ::HPSKBOM::TotalRowCells {pRows pColumns} {
    set lTotalQty 0
    foreach lRow $pRows { incr lTotalQty [dict get $lRow qty] }

    set lCells [list]
    set lIdx 0
    foreach lCol $pColumns {
        if {$lIdx == 0} {
            lappend lCells "Total"
        } elseif {[dict get $lCol kind] eq "qty"} {
            lappend lCells $lTotalQty
        } else {
            lappend lCells ""
        }
        incr lIdx
    }
    return $lCells
}

proc ::HPSKBOM::GetDesignFilePath {} {
    if {[catch {GetActivePMDesign} lDesign]} { return "" }
    if {$lDesign eq "" || $lDesign eq "NULL" || $lDesign == 1} { return "" }
    set lName [DboTclHelper_sMakeCString]
    if {[catch {$lDesign GetName $lName}]} { return "" }
    return [DboTclHelper_sGetConstCharPtr $lName]
}

proc ::HPSKBOM::GetDesignFileName {} {
    set lPath [::HPSKBOM::GetDesignFilePath]
    if {$lPath eq ""} { return "" }
    return [file tail $lPath]
}

# CSV -> .csv, TXT -> .txt, HTML -> .html (anything else falls back to .csv)
proc ::HPSKBOM::FormatExtension {pFormat} {
    switch -- [string toupper $pFormat] {
        TXT  { return ".txt"  }
        HTML { return ".html" }
        default { return ".csv" }
    }
}

# Default output path with no extension: <activeDesignDir>\<activeDesignBaseName>.
# Falls back to <HomeDir>\HPSK_BOM when no design is open/saved yet.
proc ::HPSKBOM::DefaultOutputBase {} {
    set lPath [::HPSKBOM::GetDesignFilePath]
    if {$lPath eq ""} {
        return [file join [::HPSKBOM::HomeDir] "HPSK_BOM"]
    }
    return [file join [file dirname $lPath] [file rootname [file tail $lPath]]]
}

proc ::HPSKBOM::MonthAbbrEN {pMonthNum} {
    set lNames {Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec}
    if {$pMonthNum < 1 || $pMonthNum > 12} { return "" }
    return [lindex $lNames [expr {$pMonthNum - 1}]]
}

# Header template placeholders:
#   <filename>  active design file name
#   <YYYY>      4-digit year          <MM>  2-digit month   <DD>  2-digit day
#   <EE>        English month abbreviation (Jan, Feb, ... Dec), always in
#               English regardless of Windows locale
proc ::HPSKBOM::ResolveHeaderPlaceholders {pTemplate} {
    if {[string trim $pTemplate] eq ""} { return "" }

    set lNow      [clock seconds]
    set lYear     [clock format $lNow -format "%Y"]
    set lMonth    [clock format $lNow -format "%m"]
    set lDay      [clock format $lNow -format "%d"]
    set lMonthNum [scan $lMonth "%d"]
    set lMonthEn  [::HPSKBOM::MonthAbbrEN $lMonthNum]
    set lFileName [::HPSKBOM::GetDesignFileName]

    return [string map [list \
        "<filename>" $lFileName \
        "<YYYY>" $lYear \
        "<MM>" $lMonth \
        "<DD>" $lDay \
        "<EE>" $lMonthEn] $pTemplate]
}

proc ::HPSKBOM::HeaderPlaceholderHint {} {
    return "예)\n*****************\ndesign file : <filename>\nDate : <EE> <DD>, <YYYY>\n*****************"
}

# Returns {text totalRowCount truncated}
proc ::HPSKBOM::GenerateBomText {pMaxRows} {
    variable mFormat
    variable mDelimiter
    variable mHeaderTemplate

    set lActiveFields [::HPSKBOM::CollectActiveFields]
    set lColumns      [::HPSKBOM::BuildColumns $lActiveFields]
    set lHeaderCells  [list]
    foreach lCol $lColumns { lappend lHeaderCells [dict get $lCol label] }

    set lRows [::HPSKBOM::GroupPartsForExport $lActiveFields]

    set lHeaderBlock [string trim [::HPSKBOM::ResolveHeaderPlaceholders $mHeaderTemplate]]

    set lTotalRows [llength $lRows]
    set lTotalCells [::HPSKBOM::TotalRowCells $lRows $lColumns]

    set lTruncated 0
    if {$pMaxRows > 0 && $lTotalRows > $pMaxRows} {
        set lRows [lrange $lRows 0 [expr {$pMaxRows - 1}]]
        set lTruncated 1
    }

    set lFormatUpper [string toupper $mFormat]
    set lBuf ""

    if {$lFormatUpper eq "HTML"} {
        append lBuf "<html>\n<head>\n<meta charset=\"utf-8\">\n<title>HPSK_BOM</title>\n"
        append lBuf "<style>table\{border-collapse:collapse;font-family:sans-serif;font-size:12px;\}"
        append lBuf "th,td\{border:1px solid #888;padding:4px 8px;\}th\{background:#eee;\}"
        append lBuf "pre\{font-family:monospace;\}</style>\n"
        append lBuf "</head>\n<body>\n"
        if {$lHeaderBlock ne ""} {
            append lBuf "<pre>[::HPSKBOM::HtmlEscape $lHeaderBlock]</pre>\n"
        }
        append lBuf "<table>\n<tr>"
        foreach c $lHeaderCells { append lBuf "<th>[::HPSKBOM::HtmlEscape $c]</th>" }
        append lBuf "</tr>\n"
        foreach lRow $lRows {
            append lBuf "<tr>"
            foreach c [::HPSKBOM::RowCells $lRow $lColumns] { append lBuf "<td>[::HPSKBOM::HtmlEscape $c]</td>" }
            append lBuf "</tr>\n"
        }
        append lBuf "<tr style=\"font-weight:bold;border-top:2px solid #333;\">"
        foreach c $lTotalCells { append lBuf "<td>[::HPSKBOM::HtmlEscape $c]</td>" }
        append lBuf "</tr>\n"
        append lBuf "</table>\n</body>\n</html>\n"
    } else {
        set lQuote [expr {$lFormatUpper eq "CSV"}]
        if {$lHeaderBlock ne ""} {
            append lBuf $lHeaderBlock
            append lBuf "\n\n"
        }
        append lBuf [::HPSKBOM::JoinRow $lHeaderCells $mDelimiter $lQuote]
        append lBuf "\n"
        foreach lRow $lRows {
            append lBuf [::HPSKBOM::JoinRow [::HPSKBOM::RowCells $lRow $lColumns] $mDelimiter $lQuote]
            append lBuf "\n"
        }
        append lBuf [::HPSKBOM::JoinRow $lTotalCells $mDelimiter $lQuote]
        append lBuf "\n"
    }

    if {$lTruncated} {
        append lBuf "\n... (미리보기는 처음 $pMaxRows 행만 표시됩니다. 전체 $lTotalRows 행)\n"
    }

    return [list $lBuf $lTotalRows $lTruncated]
}

#/////////////////////////////////////////////////////////////////////////////////
# Preset <-> UI synchronization
#/////////////////////////////////////////////////////////////////////////////////

proc ::HPSKBOM::RefreshPresetList {} {
    variable mPresetsData
    variable mPresetCombo
    if {$mPresetCombo eq "" || "" eq [info commands $mPresetCombo]} { return }
    set lNames [lsort -dictionary [dict keys $mPresetsData]]
    $mPresetCombo configure -values $lNames
}

proc ::HPSKBOM::ApplyPresetToUi {pName} {
    variable mPresetsData
    variable mFields
    variable mDelimiter
    variable mFormat

    if {![dict exists $mPresetsData $pName]} { return }
    set lPreset [dict get $mPresetsData $pName]

    set lSavedFields [dict create]
    foreach lF [dict get $lPreset fields] {
        dict set lSavedFields [dict get $lF field] $lF
    }

    # the saved field order wins; any current field missing from the saved
    # preset (e.g. a newer design has a property this preset never saw) is
    # appended after it so nothing silently disappears from the table.
    set lNewFields [list]
    set lPlacedFieldNames [list]
    foreach lF [dict get $lPreset fields] {
        set lFieldName [dict get $lF field]
        if {![dict exists $lSavedFields $lFieldName]} { continue }
        set lCurrent [::HPSKBOM::FindFieldInList $mFields $lFieldName]
        if {$lCurrent eq ""} { continue }
        set lInclude [dict get $lF include]
        if {[::HPSKBOM::IsLockedField $lFieldName]} { set lInclude 1 }
        lappend lNewFields [dict create field $lFieldName \
            bomName [dict get $lF bomName] include $lInclude]
        lappend lPlacedFieldNames $lFieldName
    }
    foreach lF $mFields {
        set lFieldName [dict get $lF field]
        if {[lsearch -exact $lPlacedFieldNames $lFieldName] < 0} {
            lappend lNewFields $lF
        }
    }
    set mFields $lNewFields

    set mDelimiter [dict get $lPreset delimiter]
    set mFormat    [dict get $lPreset format]
    ::HPSKBOM::SyncOutputFileExtension
    ::HPSKBOM::SetHeaderTemplateText [dict get $lPreset headerTemplate]

    ::HPSKBOM::BuildFieldsTable
    ::HPSKBOM::RefreshPreview
}

proc ::HPSKBOM::FindFieldInList {pFields pFieldName} {
    foreach lF $pFields {
        if {[dict get $lF field] eq $pFieldName} { return $lF }
    }
    return ""
}

proc ::HPSKBOM::OnPresetSelected {} {
    variable mPresetsData
    variable mPresetCombo
    set lName [$mPresetCombo get]
    if {![dict exists $mPresetsData $lName]} { return }
    ::HPSKBOM::ApplyPresetToUi $lName
}

# Used by both the top preset bar's [설정 적용] button and the bottom
# button bar's [설정 적용] button - creates a new preset or overwrites
# an existing one that matches the typed/selected name.
proc ::HPSKBOM::ApplySettings {} {
    variable mPresetsData
    variable mLastPreset
    variable mPresetCombo
    variable mDelimiter
    variable mFormat
    variable mHeaderTemplate

    set lName [string trim [$mPresetCombo get]]
    if {$lName eq ""} {
        capAppUtils::showError "HPSK_BOM" "설정 이름을 입력해 주세요."
        return 0
    }

    set lFields [::HPSKBOM::CollectActiveFields]
    dict set mPresetsData $lName [dict create \
        delimiter $mDelimiter format $mFormat headerTemplate $mHeaderTemplate \
        fields $lFields]
    set mLastPreset $lName

    ::HPSKBOM::RefreshPresetList
    $mPresetCombo set $lName

    return [::HPSKBOM::SaveStore]
}

#/////////////////////////////////////////////////////////////////////////////////
# UI
#/////////////////////////////////////////////////////////////////////////////////

proc ::HPSKBOM::OnFieldsChanged {args} {
    ::HPSKBOM::RefreshPreview
}

# When the output file is still untouched (blank) or still sitting at the
# auto-generated <designDir>\<designName> base, follow the format selector
# and swap its extension too. A path the user has customized (typed a
# different name/folder via the entry or [찾아보기...]) is left alone.
proc ::HPSKBOM::SyncOutputFileExtension {} {
    variable mOutputFile
    variable mFormat

    set lDefaultBase [::HPSKBOM::DefaultOutputBase]
    set lCurrentBase [file join [file dirname $mOutputFile] [file rootname [file tail $mOutputFile]]]
    if {[string trim $mOutputFile] eq "" || $lCurrentBase eq $lDefaultBase} {
        set mOutputFile "$lDefaultBase[::HPSKBOM::FormatExtension $mFormat]"
    }
}

proc ::HPSKBOM::OnFormatChanged {} {
    ::HPSKBOM::SyncOutputFileExtension
    ::HPSKBOM::OnFieldsChanged
}

# checkbuttons are bound directly to mIncludeVars($field) via -variable, so
# just writing the array elements is enough to refresh every checkbox on
# screen - no need to rebuild the fields table.
proc ::HPSKBOM::SetAllFieldsInclude {pValue} {
    variable mFields
    variable mIncludeVars

    foreach lF $mFields {
        set lFieldName [dict get $lF field]
        set mIncludeVars($lFieldName) [expr {[::HPSKBOM::IsLockedField $lFieldName] ? 1 : $pValue}]
    }
    ::HPSKBOM::OnFieldsChanged
}

# Reorders mFields (after syncing any pending checkbox/name edits from the
# live widgets first, so a reorder click never discards unsaved changes),
# then rebuilds the fields table to reflect the new order.
proc ::HPSKBOM::MoveField {pFieldName pDirection} {
    variable mFields

    set mFields [::HPSKBOM::CollectActiveFields]

    set lIdx  -1
    set lLen  [llength $mFields]
    for {set i 0} {$i < $lLen} {incr i} {
        if {[dict get [lindex $mFields $i] field] eq $pFieldName} { set lIdx $i; break }
    }
    if {$lIdx < 0} { return }

    set lNewIdx [expr {$pDirection eq "up" ? $lIdx - 1 : $lIdx + 1}]
    if {$lNewIdx < 0 || $lNewIdx >= $lLen} { return }

    set lItem   [lindex $mFields $lIdx]
    set mFields [lreplace $mFields $lIdx $lIdx]
    set mFields [linsert $mFields $lNewIdx $lItem]

    ::HPSKBOM::BuildFieldsTable
    ::HPSKBOM::OnFieldsChanged
}

proc ::HPSKBOM::MoveFieldUp   {pFieldName} { ::HPSKBOM::MoveField $pFieldName "up" }
proc ::HPSKBOM::MoveFieldDown {pFieldName} { ::HPSKBOM::MoveField $pFieldName "down" }

#/////////////////////////////////////////////////////////////////////////////////
# 머리글 (header template) box - shows a greyed-out placeholder hint (listing
# the available <..> tokens) whenever it is empty, like a standard "ghost
# text" input hint. mHeaderTemplate always holds the real, substitutable
# template text - it is "" whenever the placeholder hint is being shown.
#/////////////////////////////////////////////////////////////////////////////////

proc ::HPSKBOM::SetHeaderTemplateText {pText} {
    variable mHeaderText
    variable mHeaderTemplate
    variable mHeaderIsPlaceholder

    if {$mHeaderText eq "" || "" eq [info commands $mHeaderText]} {
        set mHeaderTemplate $pText
        return
    }

    $mHeaderText delete 1.0 end
    if {[string trim $pText] eq ""} {
        $mHeaderText insert end [::HPSKBOM::HeaderPlaceholderHint]
        $mHeaderText configure -foreground "#999999"
        set mHeaderIsPlaceholder 1
        set mHeaderTemplate ""
    } else {
        $mHeaderText insert end $pText
        $mHeaderText configure -foreground "black"
        set mHeaderIsPlaceholder 0
        set mHeaderTemplate $pText
    }
}

proc ::HPSKBOM::OnHeaderFocusIn {pWidget} {
    variable mHeaderIsPlaceholder
    if {$mHeaderIsPlaceholder} {
        $pWidget delete 1.0 end
        $pWidget configure -foreground "black"
        set mHeaderIsPlaceholder 0
    }
}

proc ::HPSKBOM::OnHeaderFocusOut {pWidget} {
    variable mHeaderTemplate
    variable mHeaderIsPlaceholder

    set lContent [string trim [$pWidget get 1.0 end]]
    if {$lContent eq ""} {
        $pWidget delete 1.0 end
        $pWidget insert end [::HPSKBOM::HeaderPlaceholderHint]
        $pWidget configure -foreground "#999999"
        set mHeaderIsPlaceholder 1
        set mHeaderTemplate ""
    }
}

proc ::HPSKBOM::OnHeaderKeyRelease {pWidget} {
    variable mHeaderTemplate
    variable mHeaderIsPlaceholder
    if {$mHeaderIsPlaceholder} { return }
    set mHeaderTemplate [$pWidget get 1.0 end-1c]
    ::HPSKBOM::OnFieldsChanged
}

proc ::HPSKBOM::RefreshPreview {} {
    variable mPreviewText
    if {$mPreviewText eq "" || "" eq [info commands $mPreviewText]} { return }

    set lResult [::HPSKBOM::GenerateBomText 50]
    set lText   [lindex $lResult 0]

    $mPreviewText configure -state normal
    $mPreviewText delete 1.0 end
    $mPreviewText insert end $lText
    $mPreviewText configure -state disabled
}

proc ::HPSKBOM::BuildFieldsTable {} {
    variable mFieldsInner
    variable mFields
    variable mIncludeVars
    variable mBomNameVars

    if {$mFieldsInner eq "" || "" eq [info commands $mFieldsInner]} { return }

    foreach w [winfo children $mFieldsInner] { destroy $w }
    array unset mIncludeVars
    array unset mBomNameVars
    array set mIncludeVars {}
    array set mBomNameVars {}

    ttk::label $mFieldsInner.hInc -text "포함"
    ttk::label $mFieldsInner.hFld -text "필드"
    ttk::label $mFieldsInner.hBom -text "BOM 이름"
    ttk::label $mFieldsInner.hOrd -text "순서"
    grid $mFieldsInner.hInc -row 0 -column 0 -sticky w  -padx 4 -pady 2
    grid $mFieldsInner.hFld -row 0 -column 1 -sticky w  -padx 4 -pady 2
    grid $mFieldsInner.hBom -row 0 -column 2 -sticky ew -padx 4 -pady 2
    grid $mFieldsInner.hOrd -row 0 -column 3 -sticky w  -padx 4 -pady 2 -columnspan 2

    set lRow  1
    set lLast [expr {[llength $mFields] - 1}]
    set lIdx  0
    foreach lF $mFields {
        set lFieldName [dict get $lF field]
        set lLocked    [::HPSKBOM::IsLockedField $lFieldName]

        set mIncludeVars($lFieldName) [expr {$lLocked ? 1 : [dict get $lF include]}]
        set mBomNameVars($lFieldName) [dict get $lF bomName]

        set lChk [ttk::checkbutton $mFieldsInner.chk$lRow \
            -variable ::HPSKBOM::mIncludeVars($lFieldName) \
            -command ::HPSKBOM::OnFieldsChanged]
        if {$lLocked} { $lChk configure -state disabled }

        set lLblText $lFieldName
        if {$lLocked} { append lLblText " (항상 포함)" }
        set lLbl [ttk::label $mFieldsInner.lbl$lRow -text $lLblText]

        set lEnt [ttk::entry $mFieldsInner.ent$lRow \
            -textvariable ::HPSKBOM::mBomNameVars($lFieldName)]
        bind $lEnt <KeyRelease> ::HPSKBOM::OnFieldsChanged

        set lUpBtn [ttk::button $mFieldsInner.up$lRow -text "U" -width 2 \
            -command [list ::HPSKBOM::MoveFieldUp $lFieldName]]
        set lDnBtn [ttk::button $mFieldsInner.dn$lRow -text "D" -width 2 \
            -command [list ::HPSKBOM::MoveFieldDown $lFieldName]]
        if {$lIdx == 0}     { $lUpBtn configure -state disabled }
        if {$lIdx == $lLast} { $lDnBtn configure -state disabled }

        grid $lChk   -row $lRow -column 0 -sticky w  -padx 4 -pady 1
        grid $lLbl   -row $lRow -column 1 -sticky w  -padx 4 -pady 1
        grid $lEnt   -row $lRow -column 2 -sticky ew -padx 4 -pady 1
        grid $lUpBtn -row $lRow -column 3 -sticky w  -padx 1 -pady 1
        grid $lDnBtn -row $lRow -column 4 -sticky w  -padx 1 -pady 1

        incr lRow
        incr lIdx
    }
    grid columnconfigure $mFieldsInner 2 -weight 1
}

proc ::HPSKBOM::OnInnerConfigure {pCanvas} {
    $pCanvas configure -scrollregion [$pCanvas bbox all]
}

proc ::HPSKBOM::OnCanvasConfigure {pCanvas pWinId} {
    $pCanvas itemconfigure $pWinId -width [winfo width $pCanvas]
}

proc ::HPSKBOM::MakeScrollFrame {pParent} {
    set lCanvas [canvas $pParent.canvas -highlightthickness 0]
    set lVsb [ttk::scrollbar $pParent.vsb -orient vertical -command [list $lCanvas yview]]
    $lCanvas configure -yscrollcommand [list $lVsb set]

    grid $lCanvas -row 0 -column 0 -sticky nsew
    grid $lVsb    -row 0 -column 1 -sticky ns
    grid rowconfigure $pParent 0 -weight 1
    grid columnconfigure $pParent 0 -weight 1

    set lInner [ttk::frame $lCanvas.inner]
    set lWinId [$lCanvas create window 0 0 -anchor nw -window $lInner]

    bind $lInner  <Configure> [list ::HPSKBOM::OnInnerConfigure $lCanvas]
    bind $lCanvas <Configure> [list ::HPSKBOM::OnCanvasConfigure $lCanvas $lWinId]
    bind $lCanvas <MouseWheel> {%W yview scroll [expr {-1 * (%D / 120)}] units}

    return $lInner
}

proc ::HPSKBOM::BrowseOutputFile {} {
    variable mFormat
    variable mOutputFile

    set lExt [::HPSKBOM::FormatExtension $mFormat]
    set lTypes {
        {{CSV Files}  {.csv}}
        {{Text Files} {.txt}}
        {{HTML Files} {.html}}
        {{All Files}  {*}}
    }

    # "" -> [file dirname ""] is "." (Capture's current working directory),
    # which can silently be a slow/disconnected network project folder and
    # make the native Save dialog appear to hang. Only trust an initialdir
    # that came from an actual previously-chosen output path.
    set lInitDir ""
    if {[string trim $mOutputFile] ne ""} {
        set lCandidate [file dirname $mOutputFile]
        if {$lCandidate ne "." && [file isdirectory $lCandidate]} {
            set lInitDir $lCandidate
        }
    }
    if {$lInitDir eq ""} { set lInitDir [::HPSKBOM::HomeDir] }

    set lFile [tk_getSaveFile -defaultextension $lExt -filetypes $lTypes \
        -initialdir $lInitDir -title "HPSK_BOM 출력 파일 선택"]
    if {$lFile ne ""} {
        set mOutputFile $lFile
        ::HPSKBOM::OnFieldsChanged
    }
}

proc ::HPSKBOM::DoExport {} {
    variable mOutputFile

    if {[string trim $mOutputFile] eq ""} {
        capAppUtils::showError "HPSK_BOM" "출력 파일을 지정해 주세요."
        return
    }

    set lResult [::HPSKBOM::GenerateBomText -1]
    set lText   [lindex $lResult 0]

    if {[catch {
        set lFh [open $mOutputFile w]
        fconfigure $lFh -encoding utf-8
        puts -nonewline $lFh $lText
        close $lFh
    } lErr]} {
        capAppUtils::showError "HPSK_BOM" "BOM 파일을 저장하는 중 오류가 발생했습니다:\n$lErr"
        return
    }

    catch {AddFileToOutputFolder $mOutputFile}
    tk_messageBox -type ok -title "HPSK_BOM" -message "BOM 파일이 저장되었습니다:\n$mOutputFile"
}

proc ::HPSKBOM::DoOk {} {
    variable mForm
    if {[::HPSKBOM::ApplySettings]} {
        destroy $mForm
    }
}

proc ::HPSKBOM::BuildUi {pForm} {
    variable mVersionString
    variable mPresetCombo
    variable mFieldsInner
    variable mPreviewText
    variable mHeaderText
    variable mDelimiter
    variable mFormat
    variable mOutputFile

    grid rowconfigure    $pForm 0 -weight 1
    grid columnconfigure $pForm 0 -weight 1

    set lPaned [panedwindow $pForm.paned -orient horizontal]
    grid $lPaned -row 0 -column 0 -sticky nsew -padx 4 -pady 4

    set lLeft  [ttk::frame $lPaned.left]
    set lRight [ttk::frame $lPaned.right]
    $lPaned add $lLeft  -width 300
    $lPaned add $lRight -width 480

    # ------------------------------------------------------------------ Left
    grid rowconfigure    $lLeft 1 -weight 1
    grid columnconfigure $lLeft 0 -weight 1

    set lPresetFrame [ttk::labelframe $lLeft.presetFrame -text "저장된 설정"]
    grid $lPresetFrame -row 0 -column 0 -sticky ew -padx 2 -pady 2
    grid columnconfigure $lPresetFrame 1 -weight 1

    ttk::label $lPresetFrame.lbl -text "이름:"
    set mPresetCombo [ttk::combobox $lPresetFrame.combo -width 18]
    bind $mPresetCombo <<ComboboxSelected>> ::HPSKBOM::OnPresetSelected
    # only one [설정 적용] button exists, in the bottom button bar - see
    # $pForm.btnBar.applyBtn in this same proc.

    grid $lPresetFrame.lbl      -row 0 -column 0 -padx 4 -pady 6 -sticky w
    grid $lPresetFrame.combo    -row 0 -column 1 -padx 4 -pady 6 -sticky ew

    set lFieldsFrame [ttk::labelframe $lLeft.fieldsFrame -text "필드 (체크한 항목만 BOM에 출력됩니다)"]
    grid $lFieldsFrame -row 1 -column 0 -sticky nsew -padx 2 -pady 2
    grid rowconfigure    $lFieldsFrame 1 -weight 1
    grid columnconfigure $lFieldsFrame 0 -weight 1

    set lFieldsBtnBar [ttk::frame $lFieldsFrame.btnBar]
    grid $lFieldsBtnBar -row 0 -column 0 -sticky w -padx 2 -pady 2

    ttk::button $lFieldsBtnBar.allOn  -text "모두 켜기" -command {::HPSKBOM::SetAllFieldsInclude 1}
    ttk::button $lFieldsBtnBar.allOff -text "모두 끄기" -command {::HPSKBOM::SetAllFieldsInclude 0}
    grid $lFieldsBtnBar.allOn  -row 0 -column 0 -padx 2
    grid $lFieldsBtnBar.allOff -row 0 -column 1 -padx 2

    set lFieldsScrollHolder [ttk::frame $lFieldsFrame.scrollHolder]
    grid $lFieldsScrollHolder -row 1 -column 0 -sticky nsew

    set mFieldsInner [::HPSKBOM::MakeScrollFrame $lFieldsScrollHolder]

    # ----------------------------------------------------------------- Right
    grid rowconfigure    $lRight 2 -weight 1
    grid columnconfigure $lRight 0 -weight 1

    # Row 1 : output file
    set lOutFrame [ttk::frame $lRight.outFrame]
    grid $lOutFrame -row 0 -column 0 -sticky ew -padx 2 -pady 4
    grid columnconfigure $lOutFrame 1 -weight 1

    ttk::label  $lOutFrame.lbl -text "출력 파일:"
    ttk::entry  $lOutFrame.entry -textvariable ::HPSKBOM::mOutputFile
    ttk::button $lOutFrame.browse -text "찾아보기..." -command ::HPSKBOM::BrowseOutputFile
    bind $lOutFrame.entry <KeyRelease> ::HPSKBOM::OnFieldsChanged

    grid $lOutFrame.lbl    -row 0 -column 0 -sticky w  -padx 4
    grid $lOutFrame.entry  -row 0 -column 1 -sticky ew -padx 4
    grid $lOutFrame.browse -row 0 -column 2 -sticky e  -padx 4

    # Row 2 : delimiter + format
    set lFmtFrame [ttk::frame $lRight.fmtFrame]
    grid $lFmtFrame -row 1 -column 0 -sticky ew -padx 2 -pady 4

    ttk::label $lFmtFrame.lblDelim -text "구분자:"
    ttk::entry $lFmtFrame.entryDelim -width 4 -textvariable ::HPSKBOM::mDelimiter
    ttk::label $lFmtFrame.lblFmt -text "형식:"
    ttk::combobox $lFmtFrame.comboFmt -width 8 -state readonly \
        -values {CSV TXT HTML} -textvariable ::HPSKBOM::mFormat

    bind $lFmtFrame.entryDelim <KeyRelease> ::HPSKBOM::OnFieldsChanged
    bind $lFmtFrame.comboFmt <<ComboboxSelected>> ::HPSKBOM::OnFormatChanged

    grid $lFmtFrame.lblDelim   -row 0 -column 0 -sticky w -padx 4
    grid $lFmtFrame.entryDelim -row 0 -column 1 -sticky w -padx 4
    grid $lFmtFrame.lblFmt     -row 0 -column 2 -sticky w -padx 12
    grid $lFmtFrame.comboFmt   -row 0 -column 3 -sticky w -padx 4

    # Row 2 : header template + preview, in a vertical paned (draggable
    # sash) area so the user can resize either box.
    set lHdrPrevPaned [panedwindow $lRight.hdrPrevPaned -orient vertical]
    grid $lHdrPrevPaned -row 2 -column 0 -sticky nsew -padx 2 -pady 4

    set lHdrFrame [ttk::labelframe $lHdrPrevPaned.hdrFrame -text "머리글"]
    grid rowconfigure    $lHdrFrame 0 -weight 1
    grid columnconfigure $lHdrFrame 0 -weight 1

    set mHeaderText [text $lHdrFrame.text -wrap word -height 5 -foreground "#999999"]
    ttk::scrollbar $lHdrFrame.vsb -orient vertical -command [list $mHeaderText yview]
    $mHeaderText configure -yscrollcommand [list $lHdrFrame.vsb set]
    grid $mHeaderText   -row 0 -column 0 -sticky nsew
    grid $lHdrFrame.vsb -row 0 -column 1 -sticky ns

    $mHeaderText insert end [::HPSKBOM::HeaderPlaceholderHint]
    bind $mHeaderText <FocusIn>    [list ::HPSKBOM::OnHeaderFocusIn %W]
    bind $mHeaderText <FocusOut>   [list ::HPSKBOM::OnHeaderFocusOut %W]
    bind $mHeaderText <KeyRelease> [list ::HPSKBOM::OnHeaderKeyRelease %W]

    set lPrevFrame [ttk::labelframe $lHdrPrevPaned.prevFrame -text "미리보기"]
    grid rowconfigure    $lPrevFrame 0 -weight 1
    grid columnconfigure $lPrevFrame 0 -weight 1

    set mPreviewText [text $lPrevFrame.text -wrap none -height 15]
    ttk::scrollbar $lPrevFrame.vsb -orient vertical   -command [list $mPreviewText yview]
    ttk::scrollbar $lPrevFrame.hsb -orient horizontal -command [list $mPreviewText xview]
    $mPreviewText configure \
        -yscrollcommand [list $lPrevFrame.vsb set] \
        -xscrollcommand [list $lPrevFrame.hsb set]

    grid $mPreviewText      -row 0 -column 0 -sticky nsew
    grid $lPrevFrame.vsb    -row 0 -column 1 -sticky ns
    grid $lPrevFrame.hsb    -row 1 -column 0 -sticky ew
    $mPreviewText configure -state disabled

    $lHdrPrevPaned add $lHdrFrame  -height 90  -stretch never
    $lHdrPrevPaned add $lPrevFrame -height 260 -stretch always

    # ------------------------------------------------------- Row 5 : status bar
    set lBottomBar [ttk::frame $pForm.bottomBar]
    grid $lBottomBar -row 1 -column 0 -sticky ew -padx 6 -pady 8
    grid columnconfigure $lBottomBar 0 -weight 1

    ttk::label $lBottomBar.version -text $mVersionString -foreground "#666666"
    grid $lBottomBar.version -row 0 -column 0 -sticky w

    set lBtnBar [ttk::frame $lBottomBar.btnBar]
    grid $lBtnBar -row 0 -column 1 -sticky e

    ttk::button $lBtnBar.exportBtn -text "내보내기"   -command ::HPSKBOM::DoExport
    ttk::button $lBtnBar.applyBtn  -text "설정 적용"  -command ::HPSKBOM::ApplySettings
    ttk::button $lBtnBar.okBtn     -text "확인"       -command ::HPSKBOM::DoOk

    grid $lBtnBar.exportBtn -row 0 -column 0 -padx 4
    grid $lBtnBar.applyBtn  -row 0 -column 1 -padx 4
    grid $lBtnBar.okBtn     -row 0 -column 2 -padx 4
}

#/////////////////////////////////////////////////////////////////////////////////
# Entry points
#/////////////////////////////////////////////////////////////////////////////////

proc ::HPSKBOM::Init {} {
    variable mForm
    variable mPresetsData
    variable mLastPreset
    variable mPresetCombo

    if {![::HPSKBOM::ScanDesign]} {
        tk_messageBox -type ok -title "HPSK_BOM" \
            -message "활성화된 디자인이 없습니다. 프로젝트를 열고 다시 시도해 주세요."
        return
    }

    ::HPSKBOM::LoadStore

    set lForm ".hpskBomDlg"
    set mForm $lForm
    if {"" eq [info commands $lForm]} {
        capAppUtils::capTopLevel $lForm
        ::HPSKBOM::BuildUi $lForm
        capAppUtils::setWindowSize $lForm 640 480 2400 1600
        wm title $lForm "HPSK_BOM"
        capAppUtils::autoAdoptWindow $lForm
    }

    ::HPSKBOM::RefreshPresetList

    set lInitial $mLastPreset
    if {![dict exists $mPresetsData $lInitial]} {
        if {[dict exists $mPresetsData "Default"]} {
            set lInitial "Default"
        } else {
            set lInitial ""
        }
    }
    $mPresetCombo set $lInitial

    if {$lInitial ne "" && [dict exists $mPresetsData $lInitial]} {
        ::HPSKBOM::ApplyPresetToUi $lInitial
    } else {
        ::HPSKBOM::SyncOutputFileExtension
        ::HPSKBOM::BuildFieldsTable
        ::HPSKBOM::RefreshPreview
    }

    if {0 == [winfo ismapped $lForm]} { wm deiconify $lForm }
    raise $lForm
    focus $lForm
}

proc ::HPSKBOM::launch {args} {
    if {[catch {::HPSKBOM::Init} lErr]} {
        catch {capAppUtils::showError "HPSK_BOM" "HPSK_BOM 실행 중 오류가 발생했습니다:\n$lErr"}
    }
}

# end of file
