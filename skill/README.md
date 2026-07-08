Skill 폴더
======================
사용자가 작성한 확장 프로그램을 저장하는 경로
* 확장자는 .il

HPSK_askii.il : 설계된 PCB 데이터를 ASCII 데이터로 출력하는 기능
 - 명령어 : create ascii

HPSK_AutoRefdes.il : 레퍼런스를 정리하는 기능
 - 명령어 : auto_refdes
 - 사용방법 : il 파일안에 블록 크기와 정렬을 선택
   - 블록 설정 : HPSK_tText_Blk이며 기본값은 "3"
   - 글자 정렬 : HPSK_tText_Jus이며 "LEFT", "CENTER", "RIGHT" 중 입력

HPSK_export_pad.il : PAD 데이터를 추출하는 기능
 - 명령어 : export pad

HPSK_visible_color.il : 사용자가 설정한 Color를 보이고 숨기는 기능
 - 사용자 Color 보이게 설정 명령어 : color on
 - 사용자 Color 숨기는 설정 명령어 : color off