procedure(_HP_View_Custom()
   axlDBDisplayControl('customColorEnabled t)
   axlVisibleDesign(t)
   axlUIWRedraw(nil)
)

procedure(_HP_Hide_Custom()
   axlDBDisplayControl('customColorEnabled nil)
   axlVisibleDesign(t)
   axlUIWRedraw(nil)
)

axlCmdRegister("color on" '_HP_View_Custom ?cmdType "sub_cmd")
axlCmdRegister("color off" '_HP_Hide_Custom ?cmdType "sub_cmd")