# Tcl package index file, version 1.1
# This file is sourced either when an application starts up or
# by a "package unknown" script.  It invokes the "package ifneeded"
# command to set up package-related information so that packages
# will be loaded automatically in response to "package require"
# commands. When this script is sourced, the variable $dir must
# contain the full path name of this file's directory.
#
# NOTE: capHPSKBOM.tcl contains Korean (UTF-8) text, so it is
#       explicitly sourced with -encoding utf-8 regardless of the
#       Windows system locale.

package ifneeded capHPSKBOM 1.0 [list source -encoding utf-8 [file join $dir capHPSKBOM.tcl]]
