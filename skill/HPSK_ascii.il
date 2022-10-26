/*
################################################################################
#                                                                              #
#                      Command: create ascii                                   #
#                   Skill File: HPSK_ascii.il                                  #
#                                                                              #
#                       Author: 행복찾기                                       #
#                        Blog : orcad.pe.kr                                    #
#                        Email: kingreddrake@naver.com                         #
#                Creation Date: Rev. 1.1	Jul. 18, 2019                      #
#                                                                              #
################################################################################


################################################################################
# 주의! 이 skill 파일은 공개용이며, 상업적 목적으로 판매를 금지한다.           #
#  해당 skill 파일을 pcbenv 폴더(실행창(윈도우키 + R)에서 %HOME%\pcbenv )에    #
# 복사한 다음 allegro.ilinit 파일에 다음과 같이 추가한다.					   #
# load("HPSK_ascii.il ")                                                       #
# PCB Editor의 Command 창에 create ascii 라고 입력하면 Skill이 실행된다.       #
# 실행 후 BRD 파일이 있는 경로에서 ASCII 폴더가 생성되고 출력물이 생성된다.    #
################################################################################

################################################################################
# V 1.0                                                                        #
# lay, pad, geom, comp_pin를 출력				                        	   #
################################################################################

################################################################################
# V 1.1                                                                        #
#  comp, Net 추가 출력				                                     	   #
################################################################################
*/

axlCmdRegister("create ascii" 'HPSK_create_ascii)
procedure(HPSK_create_ascii()
let(()
	;ASCII 경로 확인
	;env 파일일 내에 set ascii_dir=경로명 확인
	
	if(not(axlGetVariable("ascii_dir"))
		then
			HPSK_ASCII_dir = "ASCII"
		else
			HPSK_ASCII_dir = axlGetVariable("ascii_dir")
	)
	
	;ASCII 경로 생성
	unless(isDir(HPSK_ASCII_dir) createDir(HPSK_ASCII_dir))
	
	
	;백업 파일 관리
	
	;Lay 리포트 파일
	
	HPSK_ASCII_temp_file = strcat(HPSK_ASCII_dir "/ascii_lay.txt")
	
	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))

	HPSK_ASCII_temp_out_file = outfile(HPSK_ASCII_temp_file "w")
	
	fprintf(HPSK_ASCII_temp_out_file "LAYER\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_SORT\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_SUBCLASS\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_ARTWORK\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_USE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_CONDUCTOR\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_DIELECTRIC_CONSTANT\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_ELECTRICAL_CONDUCTIVITY\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_MATERIAL\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_SHIELD_LAYER\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_THERMAL_CONDUCTIVITY\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_THICKNESS\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_TYPE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tLAYER_LOSS_TANGENT\n")
	fprintf(HPSK_ASCII_temp_out_file "END\n")
	
	close(HPSK_ASCII_temp_out_file)
	
	;lay 파일 확인 및 출력
		
	HPSK_ASCII_lay_file = strcat(HPSK_ASCII_dir "/Lay.txt")
	when(isFile(HPSK_ASCII_lay_file)
		if( isFile(strcat(HPSK_ASCII_lay_file ",2")) then deleteFile(strcat(HPSK_ASCII_lay_file ",2")))
		if( isFile(strcat(HPSK_ASCII_lay_file ",1")) then renameFile(strcat(HPSK_ASCII_lay_file ",1") strcat(HPSK_ASCII_lay_file ",2")))
		renameFile(HPSK_ASCII_lay_file strcat(HPSK_ASCII_lay_file ",1"))
	);when

	axlExtractToFile(HPSK_ASCII_temp_file HPSK_ASCII_lay_file 'quiet)
	
	printf("Created ascii LAY file : %s\n" HPSK_ASCII_lay_file)

	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))
				
	;pad 리포트 파일
	
	HPSK_ASCII_temp_file = strcat(HPSK_ASCII_dir "/ascii_pad.txt")
	
	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))
	HPSK_ASCII_temp_out_file = outfile(HPSK_ASCII_temp_file "w")
	
	fprintf(HPSK_ASCII_temp_out_file "PAD_DEF\n")
	fprintf(HPSK_ASCII_temp_out_file "END\n")
	
	close(HPSK_ASCII_temp_out_file)
	
	;pad 파일 확인 및 출력
	
	HPSK_ASCII_pad_file = strcat(HPSK_ASCII_dir "/pad.txt")
		when(isFile(HPSK_ASCII_pad_file)
			if( isFile(strcat(HPSK_ASCII_pad_file ",2")) then deleteFile(strcat(HPSK_ASCII_pad_file ",2")))
			if( isFile(strcat(HPSK_ASCII_pad_file ",1")) then renameFile(strcat(HPSK_ASCII_pad_file ",1") strcat(HPSK_ASCII_pad_file ",2")))
			renameFile(HPSK_ASCII_pad_file strcat(HPSK_ASCII_pad_file ",1"))
		);when

	axlExtractToFile(HPSK_ASCII_temp_file HPSK_ASCII_pad_file 'quiet)
	
	printf("Created ascii PAD file : %s\n" HPSK_ASCII_pad_file)
	
	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))
	
	;GEOM 리포트 파일
	
	HPSK_ASCII_temp_file = strcat(HPSK_ASCII_dir "/ascii_geom.txt")
	
	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))
	HPSK_ASCII_temp_out_file = outfile(HPSK_ASCII_temp_file "w")
	
	fprintf(HPSK_ASCII_temp_out_file "FULL_GEOMETRY\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCLASS\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSUBCLASS\n")
	fprintf(HPSK_ASCII_temp_out_file "\tRECORD_TAG\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPIN_NO_SHAPE_CONNECT\n")
	fprintf(HPSK_ASCII_temp_out_file "\tREFDES\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_TYPE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_X\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_Y\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_ROTATE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_MIRROR\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_NUMBER\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_1\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_2\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_3\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_4\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_5\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_6\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_7\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_8\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_9\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_10\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPAD_STACK_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPIN_NUMBER\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPIN_X\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPIN_Y\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPIN_ROTATION_ABSOLUTE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tTEST_POINT\n")
	fprintf(HPSK_ASCII_temp_out_file "\tDRILL_FIGURE_CHAR\n")
	fprintf(HPSK_ASCII_temp_out_file "\tFILLET\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPACKAGE_HEIGHT_MAX\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPACKAGE_HEIGHT_MIN\n")
	fprintf(HPSK_ASCII_temp_out_file "END\n")
	
	close(HPSK_ASCII_temp_out_file)

	;geom 파일 확인 및 출력
	
	HPSK_ASCII_geom_file = strcat(HPSK_ASCII_dir "/geom.txt")
		when(isFile(HPSK_ASCII_geom_file)
			if( isFile(strcat(HPSK_ASCII_geom_file ",2")) then deleteFile(strcat(HPSK_ASCII_geom_file ",2")))
			if( isFile(strcat(HPSK_ASCII_geom_file ",1")) then renameFile(strcat(HPSK_ASCII_geom_file ",1") strcat(HPSK_ASCII_geom_file ",2")))
			renameFile(HPSK_ASCII_geom_file strcat(HPSK_ASCII_geom_file ",1"))
		);when

	axlExtractToFile(HPSK_ASCII_temp_file HPSK_ASCII_geom_file 'quiet)
	
	printf("Created ascii GEOM file : %s\n" HPSK_ASCII_geom_file)
	
	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))
	
	;COMP_PIN 리포트 파일
	
	HPSK_ASCII_temp_file = strcat(HPSK_ASCII_dir "/ascii_comp_pin.txt")
	
	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))
	HPSK_ASCII_temp_out_file = outfile(HPSK_ASCII_temp_file "w")
	
	fprintf(HPSK_ASCII_temp_out_file "COMPOSITE_PAD\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCLASS\n")
	fprintf(HPSK_ASCII_temp_out_file "\tREFDES\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_TYPE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_X\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_Y\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_ROTATE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_MIRROR\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPIN_NUMBER\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPIN_EDITED\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPAD_STACK_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSTART_LAYER_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tEND_LAYER_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPIN_X\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPIN_Y\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPIN_ROTATION_ABSOLUTE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tVIA_X\n")
	fprintf(HPSK_ASCII_temp_out_file "\tVIA_Y\n")
	fprintf(HPSK_ASCII_temp_out_file "\tVIA_ROTATION\n")
	fprintf(HPSK_ASCII_temp_out_file "\tVIA_MIRROR\n")
	fprintf(HPSK_ASCII_temp_out_file "\tDRILL_HOLE_X\n")
	fprintf(HPSK_ASCII_temp_out_file "\tDRILL_HOLE_Y\n")
	fprintf(HPSK_ASCII_temp_out_file "\tDRILL_HOLE_PLATING\n")
	fprintf(HPSK_ASCII_temp_out_file "\tDRILL_FIGURE_CHAR\n")
	fprintf(HPSK_ASCII_temp_out_file "\tDRILL_FIGURE_SHAPE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tDRILL_FIGURE_WIDTH\n")
	fprintf(HPSK_ASCII_temp_out_file "\tDRILL_FIGURE_HEIGHT\n")
	fprintf(HPSK_ASCII_temp_out_file "\tDRILL_FIGURE_ROTATION\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_1\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_2\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_3\n")
	fprintf(HPSK_ASCII_temp_out_file "\tGRAPHIC_DATA_4\n")
	fprintf(HPSK_ASCII_temp_out_file "\tDRILL_HOLE_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "END\n")

	close(HPSK_ASCII_temp_out_file)
	
	;COMP_PIN 파일 확인 및 출력
	
	HPSK_ASCII_pin_file = strcat(HPSK_ASCII_dir "/comppin.txt")
		when(isFile(HPSK_ASCII_pin_file)
			if( isFile(strcat(HPSK_ASCII_pin_file ",2")) then deleteFile(strcat(HPSK_ASCII_pin_file ",2")))
			if( isFile(strcat(HPSK_ASCII_pin_file ",1")) then renameFile(strcat(HPSK_ASCII_pin_file ",1") strcat(HPSK_ASCII_pin_file ",2")))
			renameFile(HPSK_ASCII_pin_file strcat(HPSK_ASCII_pin_file ",1"))
		);when

	axlExtractToFile(HPSK_ASCII_temp_file HPSK_ASCII_pin_file 'quiet)
	
	printf("Created ascii PIN file : %s\n" HPSK_ASCII_pin_file)
	
	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))
	
	;NET 리포트 파일
	
	HPSK_ASCII_temp_file = strcat(HPSK_ASCII_dir "/ascii_net.txt")
	
	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))
	HPSK_ASCII_temp_out_file = outfile(HPSK_ASCII_temp_file "w")
	
	fprintf(HPSK_ASCII_temp_out_file "NET\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_ASSIGN_TOPOLOGY\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_BUS_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "#\tNET_RESISTANCE\n")
	fprintf(HPSK_ASCII_temp_out_file "#\tNET_CAPACITANCE\n")
	fprintf(HPSK_ASCII_temp_out_file "#\tNET_INDUCTANCE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_VOLTAGE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_CLOCK_NET\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_DIFFERENTIAL_PAIR\n")
	fprintf(HPSK_ASCII_temp_out_file "#\tNET_IMPEDANCE_AVERAGE\n")
	fprintf(HPSK_ASCII_temp_out_file "#\tNET_IMPEDANCE_MAXIMUM\n")
	fprintf(HPSK_ASCII_temp_out_file "#\tNET_IMPEDANCE_MINIMUM\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_IMPEDANCE_RULE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_MAX_OVERSHOOT\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_MAX_PARALLEL\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_MAX_XTALK\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_MIN_HOLD\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_MIN_LINE_WIDTH\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_MIN_NECK_WIDTH\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_MIN_NOISE_MARGIN\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_NO_RAT\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_PROPAGATION_DELAY\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_RELATIVE_PROPAGATION_DELAY\n")
	fprintf(HPSK_ASCII_temp_out_file "#\tNET_VIA_COUNT\n")
	fprintf(HPSK_ASCII_temp_out_file "\tNET_WEIGHT\n")
	fprintf(HPSK_ASCII_temp_out_file "END\n")

	
	close(HPSK_ASCII_temp_out_file)
	
	;NET 파일 확인 및 출력
	
	HPSK_ASCII_net_file = strcat(HPSK_ASCII_dir "/net.txt")
		when(isFile(HPSK_ASCII_net_file)
			if( isFile(strcat(HPSK_ASCII_net_file ",2")) then deleteFile(strcat(HPSK_ASCII_net_file ",2")))
			if( isFile(strcat(HPSK_ASCII_net_file ",1")) then renameFile(strcat(HPSK_ASCII_net_file ",1") strcat(HPSK_ASCII_net_file ",2")))
			renameFile(HPSK_ASCII_net_file strcat(HPSK_ASCII_net_file ",1"))
		);when

	axlExtractToFile(HPSK_ASCII_temp_file HPSK_ASCII_net_file 'quiet)
	
	printf("Created ascii NET file : %s\n" HPSK_ASCII_net_file)
	
	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))
	
	;comp 리포트 파일
	
	HPSK_ASCII_temp_file = strcat(HPSK_ASCII_dir "/ascii_comp.txt")
	
	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))
	HPSK_ASCII_temp_out_file = outfile(HPSK_ASCII_temp_file "w")
	
	fprintf(HPSK_ASCII_temp_out_file "COMPONENT\n")
	fprintf(HPSK_ASCII_temp_out_file "\tREFDES_SORT\n")
	fprintf(HPSK_ASCII_temp_out_file "\tREFDES\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_TYPE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_NAME\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_X\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_Y\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_ROTATE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tSYM_MIRROR\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_ALT_SYMBOLS\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_CLASS\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_DEVICE_LABEL\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_DEVICE_TYPE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_HEIGHT\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_INSERTION_CODE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_MAX_POWER_DISS\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_MAX_POWER_DISS_DEVICE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_MAX_POWER_DISS_INSTANCE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_PACKAGE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_PART_NUMBER\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_ROOM\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_SIGNAL_MODEL\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_TERMINATOR_PACK\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_TOL\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_VALUE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_VOLTAGE\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_VOLT_TEMP_MODEL\n")
	fprintf(HPSK_ASCII_temp_out_file "\tCOMP_WIRE_BOND\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPACKAGE_HEIGHT_MAX\n")
	fprintf(HPSK_ASCII_temp_out_file "\tPACKAGE_HEIGHT_MIN\n")
	fprintf(HPSK_ASCII_temp_out_file "END\n")
		
	close(HPSK_ASCII_temp_out_file)
	
	;pad 파일 확인 및 출력
	
	HPSK_ASCII_comp_file = strcat(HPSK_ASCII_dir "/comp.txt")
		when(isFile(HPSK_ASCII_comp_file)
			if( isFile(strcat(HPSK_ASCII_comp_file ",2")) then deleteFile(strcat(HPSK_ASCII_comp_file ",2")))
			if( isFile(strcat(HPSK_ASCII_comp_file ",1")) then renameFile(strcat(HPSK_ASCII_comp_file ",1") strcat(HPSK_ASCII_comp_file ",2")))
			renameFile(HPSK_ASCII_comp_file strcat(HPSK_ASCII_comp_file ",1"))
		);when

	axlExtractToFile(HPSK_ASCII_temp_file HPSK_ASCII_comp_file 'quiet)
	
	printf("Created ascii PAD file : %s\n" HPSK_ASCII_comp_file)
	
	if( isFile(HPSK_ASCII_temp_file) then deleteFile(HPSK_ASCII_temp_file))
	
);let
);procedure