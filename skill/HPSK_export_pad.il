; Pad 데이터 출력
;
;      Author :  행복찾기
;        Home :  blog.naver.com/kingreddrake
;test Product :  OrCAD / Allegro
;        Date :  Jul 08, 2026
;     Version :  v0.1
;     Command :  export pad

;       사용방법 : export pad를 실행하면 사용하지 않는 PAD 데이터를 삭제하고 PAD 파일을 추출


axlCmdRegister("export pad" '_HPSK_export_pad)

procedure(_HPSK_export_pad()
   axlPurgePadstacks('padstacks nil)
   axlPadstackToDisk()
)