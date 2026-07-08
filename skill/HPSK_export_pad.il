axlCmdRegister("export pad" '_HPSK_export_pad)

procedure(_HPSK_export_pad()
   axlPurgePadstacks('padstacks nil)
   axlPadstackToDisk()
)