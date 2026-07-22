#/////////////////////////////////////////////////////////////////////////////////
#  TCL file: capHPSKBOMInit.tcl
#            Auto-load initializer that registers the "Tools > HPSK_BOM" menu
#            item in OrCAD Capture. The capHPSKBOM package itself (which
#            contains the Korean-language UI) is only loaded on first click,
#            per the OrCAD TCL guideline of not loading application packages
#            at startup time.
#
#  See tclscripts/capHPSKBOM/capHPSKBOM.tcl, HPSK_BOM.md and HPSK_BOM_CCR.md.
#/////////////////////////////////////////////////////////////////////////////////

proc capHPSKBOM_shouldProcess {args} {
    return true
}

proc capHPSKBOM_enable {args} {
    return true
}

proc capHPSKBOM_execute {args} {
    # Capture does not load Tk by default - custom Tk dialogs (toplevel,
    # ttk::*, ...) are unavailable until a script explicitly requires it.
    if {[catch {package require Tk 8.6} lErr]} {
        catch {
            capDisplayMessageBox "Tk package not found. HPSK_BOM will not run.\n$lErr" "HPSK_BOM" 0
        }
        return
    }
    # Loading Tk always creates its default root window ".". Capture has no
    # use for it, so hide it immediately - otherwise an empty, unlabeled Tk
    # window appears alongside the HPSK_BOM dialog.
    catch {wm withdraw .}
    if {[catch {package require capHPSKBOM 1.0} lErr]} {
        catch {
            tk_messageBox -type ok -title "HPSK_BOM" \
                -message "capHPSKBOM package not found. HPSK_BOM will not run.\n$lErr"
        }
        return
    }
    ::HPSKBOM::launch
}

proc capHPSKBOM_registerActions {} {
    catch {
        RegisterAction "_cdnHPSKBOMAction" "capHPSKBOM_shouldProcess" "" "capHPSKBOM_execute" ""
        RegisterAction "_cdnHPSKBOMUpdate" "capHPSKBOM_shouldProcess" "" "capHPSKBOM_enable"  ""
        InsertXMLMenu [list [list "Tools" "HPSK_BOM"] "" "" \
            [list "action" "HPSK_BOM..." "0" "_cdnHPSKBOMAction" "_cdnHPSKBOMUpdate" "" "" "" \
                "Export a customizable Bill of Materials (HPSK_BOM)"] ""]
    }
}

capHPSKBOM_registerActions

# end of file
