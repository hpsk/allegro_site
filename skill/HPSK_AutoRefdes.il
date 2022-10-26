; 레퍼런스 정리
;
;      Author :  행복찾기
;        Home :  orcad.pe.kr
;test Product :  OrCAD / Allegro
;        Date :  Feb 28, 2021
;        Version : v0.1
;     Command :  auto_refdes

axlCmdRegister("auto_refdes" 'HPSK_AUTO_REF)


procedure(HPSK_AUTO_REF()

	HPSK_sym_DB = axlDBGetDesign()->symbols

	HPSK_sym_List = nil
	
	;클래스/서브클래스
	HPSK_sym_cls = "REF DES/SILKSCREEN"

	; 최대 text 블록 번호
	;axlDBControl('maxTextBlock)

	;텍스트 블록 번호
	HPSK_tText_Blk = "3"
	;텍스트 회전 방향
	HPSK_tText_Rot = 0.0
	HPSK_tText_Mir = nil
	
	;텍스트 정렬방향
	HPSK_tText_Jus = "CENTER"


	foreach( HPSK_Sym_elm HPSK_sym_DB

		HPSK_Text_refdes = HPSK_Sym_elm->refdes
		HPSK_Text_xy = HPSK_Sym_elm->xy
		
		;Package Symbol인지 검사
		if(HPSK_Sym_elm->type == "PACKAGE"
			then
				HPSK_sym_List = append1(HPSK_sym_List HPSK_Sym_elm)
				HPSK_tText_Mir = HPSK_Sym_elm->isMirrored
				if(HPSK_tText_Mir
					then
						HPSK_sym_Lay = strcat(HPSK_sym_cls "_BOTTOM")
						HPSK_sym_Place_Lay = "PACKAGE GEOMETRY/PLACE_BOUND_BOTTOM"
					else
						HPSK_sym_Lay = strcat(HPSK_sym_cls "_TOP")
						HPSK_sym_Place_Lay = "PACKAGE GEOMETRY/PLACE_BOUND_TOP"
				);if
				
				foreach(HPSK_Sym_elm HPSK_Sym_elm->children
					if(HPSK_Sym_elm->layer == HPSK_sym_Place_Lay HPSK_Sym_P_Box = HPSK_Sym_elm->bBox );if
				);foreach
				
				foreach(HPSK_Sym_elm HPSK_Sym_elm->children
					HPSK_Text_State = nil
					
					unless(not(HPSK_Text_refdes) HPSK_Text_State = t );unless
					
					if(HPSK_Sym_elm->layer == HPSK_sym_Lay axlDeleteObject(HPSK_Sym_elm) );if
				);foreach
				
				;symbol의 배치 위치를 위한 좌표
				if(HPSK_Text_State
					then
					HPSK_Text_orient = make_axlTextOrientation(?textBlock HPSK_tText_Blk ?rotation HPSK_tText_Rot ?mirrored HPSK_tText_Mir ?justify HPSK_tText_Jus)
					HPSK_Text_DB = car(car(axlDBCreateText(HPSK_Text_refdes HPSK_Text_xy HPSK_Text_orient HPSK_sym_Lay)))
					
					;심벌 좌상
					HPSK_Sym_elm_bBox1 = min(car(car(HPSK_Sym_P_Box)) car(cadr(HPSK_Sym_P_Box))):max(cadr(car(HPSK_Sym_P_Box)) cadr(cadr(HPSK_Sym_P_Box)))
					;심벌 우상
					HPSK_Sym_elm_bBox2 = max(car(car(HPSK_Sym_P_Box)) car(cadr(HPSK_Sym_P_Box))):max(cadr(car(HPSK_Sym_P_Box)) cadr(cadr(HPSK_Sym_P_Box)))
					;시벌 좌하
					HPSK_Sym_elm_bBox3 = min(car(car(HPSK_Sym_P_Box)) car(cadr(HPSK_Sym_P_Box))):min(cadr(car(HPSK_Sym_P_Box)) cadr(cadr(HPSK_Sym_P_Box)))
					;심벌 우하
					HPSK_Sym_elm_bBox4 = max(car(car(HPSK_Sym_P_Box)) car(cadr(HPSK_Sym_P_Box))):min(cadr(car(HPSK_Sym_P_Box)) cadr(cadr(HPSK_Sym_P_Box)))
					
					HPSK_Text_DB_bBox_x = abs(car(car(HPSK_Text_DB->bBox)) - car(cadr(HPSK_Text_DB->bBox))) / 2.0
					HPSK_Text_DB_bBox_y = abs(cadr(car(HPSK_Text_DB->bBox)) - cadr(cadr(HPSK_Text_DB->bBox))) / 2.0
					
					;텍스트 배치 위치를 위한 좌표
					if(HPSK_tText_Mir
						HPSK_Text_xy = (car(HPSK_Sym_elm_bBox2) - HPSK_Text_DB_bBox_x ):(cadr(HPSK_Sym_elm_bBox2) + HPSK_Text_DB_bBox_y)
						HPSK_Text_xy = (car(HPSK_Sym_elm_bBox1) + HPSK_Text_DB_bBox_x ):(cadr(HPSK_Sym_elm_bBox1) + HPSK_Text_DB_bBox_y)
					)
					
					axlDeleteObject(HPSK_Text_DB)
					axlDBCreateText(HPSK_Text_refdes HPSK_Text_xy HPSK_Text_orient HPSK_sym_Lay HPSK_Sym_elm)
					axlDBRefreshId(HPSK_Sym_elm)
					
				);if

		);if
	);foreach
)