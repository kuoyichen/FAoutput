#include <dos.h>                   	// Include for dos
#include <io.h>                    	// Include for io
#include <iomanip>               	// Include for stream control
#include <iostream>              	// Include for stream
#include <fstream>              	// Include for stream
#include <conio.h>                 	// Include for conio
#include <stdio.h>                 	// Include for strand io
#include <math.h>                  	// Include for math
#include <ctype.h>                 	// Include for ctype
#include <string.h>                	// Include for string
#include <stdlib.h>                	// Include for strand lib
#include <dirent.h>  
#include <time.h>
#include <sstream>
#include <string> 
#include <cstdio>

using namespace std; 

int i,j,k;
char *op;

int shFileHandle;
FILE *shFile;
char *shFileName;
int size=0;
unsigned char *shbuf;

int count_pic=0;
int loc_pic[10];

int count_cod=0;
int loc_cod[50];
int size_cod[50];
int start_cod[50];
int end_cod[50];




struct cod_st {
    int mash_id;
    int cod_id;
	unsigned char cod_hex[6];
    int x;
    int y;
    int z;
};

cod_st *cod_index[50];
cod_st *cod;

FILE *bmp_color;
FILE *bmp_type;
FILE *bmp_height;
FILE *ter_txt;
FILE *ter_color;
FILE *ter_type;
FILE *ter_height;


struct ter_st {
    unsigned char hex_z;
    unsigned char hex_color;
    unsigned char hex_type;
    int int_x;
    int int_y;
    int int_z;
    int color;
    int type;
    int offset;
};

ter_st ter_index[256][256];

//---------------------------------------

void hexprint(unsigned char i){
    if(i <= 0xF){
         printf("0%x",i);
    }else{
         printf("%x",i);
    }

}
//---------------------------------------

int stoi(string b){
 int a;
 /*
  * char s[10];
  * int z=sscanf(s,"%d",&a);
  * cout<<z<<endl;
  */
 sscanf(&b[0],"%d",&a);
 //cout<<a<<endl;
 return a;
}
	
//-----------------------------------
int taxyz2hex(char *line, int line_cnt){
	char * pch;
	char cx[10];
	char cy[10];
	char cz[10];
	int x,y,z,tmp;
	unsigned char c;
	
	if(line[0]=='\0'){ // empty line no process
		return 1;
	}

	pch = strtok(line,",");		
	strcpy(cx, pch);
	pch = strtok(NULL,",");		
	strcpy(cy, pch);
	pch = strtok(NULL,",");		
	strcpy(cz, pch);
	x=atoi(cx);
	y=atoi(cy);
	z=atoi(cz);	

    c=z;
	// put into shbuf
	shbuf[149+2+line_cnt*3]=c;

	return 0;


}
//----------------------------------
int randnum(int low, int high){
    int a=(rand()%high)+low;
    //printf("The Random Number is %d .\n", a);
    return a;
}

//----------------------------------
int bmp_hight(){
    if((shFile=fopen(shFileName,"rb"))==NULL){
		//cout<<"sh File, ("<<shFileName<<") open error !\n";

	}else{
		//<<"Load ("<<shFileName<<"), ";
		//cout<<"file length = "<<filelength(fileno(shFile))<<" bytes.\n";
	}
//-----------------------------------	
	size=filelength(fileno(shFile));
	shbuf=new unsigned char[size];
    fread(shbuf,1,size,shFile); // Read Class File
	fclose(shFile);				// Close Class File
    //cout<<"Read shFile to Buffer."<<"\n";
    // 1078-66613
//--------------------------------------
// locate all terrain data
int map_type=0;
 if(size==66614){// 256x256
       int start=1078;
       for(int y=0;y<256;y++){
               for(int x=0;x<256;x++){
                       cout<<x<<","<<y<<","<<int(shbuf[start+x+y*256])<<"\n";                   
               }
       }
 }else if(size==44342){// 208x208
       int start=1078;
       for(int y=0;y<208;y++){
               for(int x=0;x<208;x++){
                       cout<<x<<","<<y<<","<<int(shbuf[start+x+y*208])<<"\n";                   
               }
       }
 }else if(size==41078){// 200x200
       int start=1078;
       for(int y=0;y<200;y++){
               for(int x=0;x<200;x++){
                       cout<<x<<","<<y<<","<<int(shbuf[start+x+y*200])<<"\n";                   
               }
       }
 }else{
    cout<<"Wrong BMP Map type.\n";
    exit(0);
 }
}


//-----------------------------------
int ext(){ // extra T2 into 3 BMP files (and 1 txt file for hight)
    if((shFile=fopen(shFileName,"rb"))==NULL){
		//cout<<"sh File, ("<<shFileName<<") open error !\n";

	}else{
		//cout<<"Load ("<<shFileName<<"), ";
		//cout<<"file length = "<<filelength(fileno(shFile))<<" bytes.\n";
	}
//-----------------------------------	
	size=filelength(fileno(shFile));
	shbuf=new unsigned char[size];
    fread(shbuf,1,size,shFile); // Read Class File
	fclose(shFile);				// Close Class File
    //cout<<"Read shFile to Buffer."<<"\n";
    
//--------------------------------------
/* type list
00 Nothing
01 Sea
02 Forest
03 Forest #1
04 Forest #2
05 Farm
06 Moose
07 Paddy #1
08 Paddy #2
09 Paddy #2
0A Palms #1
0B Palms #2
0C Palms #3
0D Trees #1
0E Trees #2
0F Trees #3
10 Water Buffalo
11 unknown
*/


// locate all terrain data
   int ter_start=0;
   if(size==199829){//196KB:APA,BAL,CUB,GRE,IRA,LFA,NSK,PGU,SPA,WTA, (color, type, hight), start left-down
       ter_start=149;
       int ter_x=0;
       int ter_y=0;
       for(int y=0;y<256;y++){
           for(int x=0;x<256;x++){
                   ter_index[x][y].hex_color=shbuf[ter_start+0+(x*3)+(y*256*3)];
                   ter_index[x][y].hex_type=shbuf[ter_start+1+(x*3)+(y*256*3)];
                   ter_index[x][y].hex_z=shbuf[ter_start+2+(x*3)+(y*256*3)];
                   ter_index[x][y].offset=ter_start+2+(x*3)+(y*256*3);
                   ter_index[x][y].int_x=x;
                   ter_index[x][y].int_y=y;
                   ter_index[x][y].type=int(ter_index[x][y].hex_type);
                   ter_index[x][y].color=int(ter_index[x][y].hex_color);
                   ter_index[x][y].int_z=int(ter_index[x][y].hex_z);
           }   
   }
        
        
   }else if(size==126899){//124KB:EGY,FRA,VLA
       ter_start=149;
       int ter_x=0;
       int ter_y=0;
       for(int y=0;y<208;y++){
           for(int x=0;x<208;x++){
                   ter_index[x][y].hex_color=shbuf[ter_start+0+(x*3)+(y*208*3)];
                   ter_index[x][y].hex_type=shbuf[ter_start+1+(x*3)+(y*208*3)];
                   ter_index[x][y].hex_z=shbuf[ter_start+2+(x*3)+(y*208*3)];
                   ter_index[x][y].offset=ter_start+2+(x*3)+(y*208*3);
                   ter_index[x][y].int_x=x;
                   ter_index[x][y].int_y=y;
                   ter_index[x][y].type=int(ter_index[x][y].hex_type);
                   ter_index[x][y].color=int(ter_index[x][y].hex_color);
                   ter_index[x][y].int_z=int(ter_index[x][y].hex_z);
           }   
   }         
   }else if(size==122024){//119KB:TVIET, (color, type, hight), start, right-down
       ter_start=149;
       int ter_x=0;
       int ter_y=0;
       for(int y=0;y<200;y++){
           for(int x=0;x<200;x++){
                   ter_index[x][y].hex_color=shbuf[ter_start+0+(x*3)+(y*200*3)];
                   ter_index[x][y].hex_type=shbuf[ter_start+1+(x*3)+(y*200*3)];
                   ter_index[x][y].hex_z=shbuf[ter_start+2+(x*3)+(y*200*3)];
                   ter_index[x][y].offset=ter_start+2+(x*3)+(y*200*3);
                   ter_index[x][y].int_x=x;
                   ter_index[x][y].int_y=y;
                   ter_index[x][y].type=int(ter_index[x][y].hex_type);
                   ter_index[x][y].color=int(ter_index[x][y].hex_color);
                   ter_index[x][y].int_z=int(ter_index[x][y].hex_z);
           }   
   } 
   }else{
         cout<<"Unknow size of terrien file\n";
         exit(0);
   
   }
   
   
   
   
//---------------------------------------
// create output file
// example: VEX_DSTTRP.SH_0_20_601.TXT
//

	// open original BMP file
    if(size==199829){//196KB:APA,BAL,CUB,GRE,IRA,LFA,NSK,PGU,SPA,WTA, (color, type, hight), start left-down
    	if((bmp_color=fopen("256_COLOR.BMP","rb"))==NULL){
			cout<<"Original BMP color file, 256.bmp, cannot be found!\n";
			exit(0);
		}
    	if((bmp_type=fopen("256_TYPE.BMP","rb"))==NULL){
			cout<<"Original BMP type file, 256.bmp, cannot be found!\n";
			exit(0);
		}
    	if((bmp_height=fopen("256_HEIGHT.BMP","rb"))==NULL){
			cout<<"Original BMP height file, 256.bmp, cannot be found!\n";
			exit(0);
		}			
    }else if(size==126899){//124KB:EGY,FRA,VLA
    	if((bmp_color=fopen("208_COLOR.BMP","rb"))==NULL){
			cout<<"Original BMP color file, 208.bmp, cannot be found!\n";
			exit(0);
		}
    	if((bmp_type=fopen("208_TYPE.BMP","rb"))==NULL){
			cout<<"Original BMP type file, 208.bmp, cannot be found!\n";
			exit(0);
		}
    	if((bmp_height=fopen("208_HEIGHT.BMP","rb"))==NULL){
			cout<<"Original BMP height file, 208.bmp, cannot be found!\n";
			exit(0);
		}	    
    }else if(size==122024){//119KB:TVIET, (color, type, hight), start, right-down
    	if((bmp_color=fopen("200_COLOR.BMP","rb"))==NULL){
			cout<<"Original BMP color file, 200.bmp, cannot be found!\n";
			exit(0);
		}
    	if((bmp_type=fopen("200_TYPE.BMP","rb"))==NULL){
			cout<<"Original BMP type file, 200.bmp, cannot be found!\n";
			exit(0);
		}
    	if((bmp_height=fopen("200_HEIGHT.BMP","rb"))==NULL){
			cout<<"Original BMP height file, 200.bmp, cannot be found!\n";
			exit(0);
		}
    }else{
    		cout<<"Original BMP file, ?.bmp, cannot be found!\n";
			exit(0);
    }

	int bmp_size=filelength(fileno(bmp_color));

	unsigned char *bmpbuf_color;
	bmpbuf_color=new unsigned char[bmp_size];
    fread(bmpbuf_color,1,bmp_size,bmp_color);
	fclose(bmp_color);
	    
	unsigned char *bmpbuf_type;
	bmpbuf_type=new unsigned char[bmp_size];
    fread(bmpbuf_type,1,bmp_size,bmp_type);
	fclose(bmp_type);

	unsigned char *bmpbuf_height;
	bmpbuf_height=new unsigned char[bmp_size];
    fread(bmpbuf_height,1,bmp_size,bmp_height);
	fclose(bmp_height);


    char tmpFileName[50];
    char tmp[20]="tmp_";
    strcat (tmp, shFileName);
    mkdir(tmp);
    //strcpy (tmp, shFileName);
    //mkdir(shFileName);

            tmpFileName[0]='\0';
            tmp[0]='\0';
            strcpy (tmpFileName, "tmp_");
            strcat (tmpFileName, shFileName);
            strcat(tmpFileName, "\\");
            strcat(tmpFileName, "TER_");
            strcat (tmpFileName, shFileName);
            strcat (tmpFileName, "_.TXT");
            if((ter_txt=fopen(tmpFileName,"wt"))==NULL){
                cout<<"tmp ter txt files create error!\n";
                exit(0);
            }else{
                fclose(ter_txt);
                // output the vertex data to each file
                ofstream fout(tmpFileName);
			if(size==199829){//196KB:APA,BAL,CUB,GRE,IRA,LFA,NSK,PGU,SPA,WTA, (color, type, hight), start left-down
           		
				   // create txt hight file
           		for(int y=0;y<256;y++){
                   for(int x=0;x<256;x++){                      
                   		fout<<ter_index[x][y].int_x<<","<<ter_index[x][y].int_y<<","<<ter_index[x][y].int_z<<"\n";
                   }
           		}
           		// create bmp file for color ---------------
	            tmpFileName[0]='\0';
            	tmp[0]='\0';
            	strcpy (tmpFileName, "tmp_");
            	strcat (tmpFileName, shFileName);
            	strcat(tmpFileName, "\\");
            	strcat(tmpFileName, "TER_");
            	strcat (tmpFileName, shFileName);
            	strcat (tmpFileName, "_COLOR_.BMP");
            	if((ter_color=fopen(tmpFileName,"wb"))==NULL){
                	cout<<"tmp ter bmp color files create error!\n";
                	exit(0);
            	}else{
					// replace color data for origin
					
           			for(int y=0;y<256;y++){
                   		for(int x=0;x<256;x++){                      
                   			bmpbuf_color[1078+x+(y*256)]=ter_index[x][y].hex_color;
                   		}
           			}
					// then write
					fwrite(bmpbuf_color,1,bmp_size,ter_color); // write Class File
					fclose(ter_color);				// Close Class File
				}
				
				
           		// create bmp file for color ---------------
	            tmpFileName[0]='\0';
            	tmp[0]='\0';
            	strcpy (tmpFileName, "tmp_");
            	strcat (tmpFileName, shFileName);
            	strcat(tmpFileName, "\\");
            	strcat(tmpFileName, "TER_");
            	strcat (tmpFileName, shFileName);
            	strcat (tmpFileName, "_COLOR_.BMP");
            	if((ter_color=fopen(tmpFileName,"wb"))==NULL){
                	cout<<"tmp ter bmp color files create error!\n";
                	exit(0);
            	}else{
					// replace color data for origin
					
           			for(int y=0;y<256;y++){
                   		for(int x=0;x<256;x++){                      
                   			bmpbuf_color[1078+x+(y*256)]=ter_index[x][y].hex_color;
                   		}
           			}
					// then write
					fwrite(bmpbuf_color,1,bmp_size,ter_color); // write Class File
					fclose(ter_color);				// Close Class File
				}
           		// create bmp file for type ---------------
	            tmpFileName[0]='\0';
            	tmp[0]='\0';
            	strcpy (tmpFileName, "tmp_");
            	strcat (tmpFileName, shFileName);
            	strcat(tmpFileName, "\\");
            	strcat(tmpFileName, "TER_");
            	strcat (tmpFileName, shFileName);
            	strcat (tmpFileName, "_TYPE_.BMP");
            	if((ter_type=fopen(tmpFileName,"wb"))==NULL){
                	cout<<"tmp ter bmp type files create error!\n";
                	exit(0);
            	}else{
					// replace type data for origin
					
           			for(int y=0;y<256;y++){
                   		for(int x=0;x<256;x++){                      
                   			bmpbuf_type[1078+x+(y*256)]=ter_index[x][y].hex_type;
                   		}
           			}
					// then write
					fwrite(bmpbuf_type,1,bmp_size,ter_type); // write Class File
					fclose(ter_type);				// Close Class File
				}
                      		// create bmp file for height---------------
	            tmpFileName[0]='\0';
            	tmp[0]='\0';
            	strcpy (tmpFileName, "tmp_");
            	strcat (tmpFileName, shFileName);
            	strcat(tmpFileName, "\\");
            	strcat(tmpFileName, "TER_");
            	strcat (tmpFileName, shFileName);
            	strcat (tmpFileName, "_HEIGHT_.BMP");
            	if((ter_height=fopen(tmpFileName,"wb"))==NULL){
                	cout<<"tmp ter bmp heightfiles create error!\n";
                	exit(0);
            	}else{
					// replace heightdata for origin
					
           			for(int y=0;y<256;y++){
                   		for(int x=0;x<256;x++){                      
                   			bmpbuf_height[1078+x+(y*256)]=ter_index[x][y].hex_z;
                   		}
           			}
					// then write
					fwrite(bmpbuf_height,1,bmp_size,ter_height); // write Class File
					fclose(ter_height);				// Close Class File
				}
    		}else if(size==126899){//124KB:EGY,FRA,VLA
                  cout<<"This MAP "<<shFileName<<" Not supported yet.\n";
                  exit(0);
    		}else if(size==122024){//119KB:TVIET, (color, type, hight), start, right-down
                  cout<<"This MAP "<<shFileName<<" Not supported yet.\n";
                  exit(0);    
    		}else{
    
    		}

                
                
            }
            







}
//---------------------------------------


int build(){
	
	char work_dir[50];
	int size;
	// load original sh file
	if((shFile=fopen(shFileName,"rb"))==NULL){
		cout<<"sh File, ("<<shFileName<<") open error !\n";
		exit(0);

	}
	
	size=filelength(fileno(shFile));
	shbuf=new unsigned char[size];
    fread(shbuf,1,size,shFile); // Read Class File
	fclose(shFile);				// Close Class File
	
	// load 3 bmp files

	work_dir[0]='\0';
    strcpy (work_dir, "tmp_");
    strcat (work_dir, shFileName);
    
    if( (_access( work_dir, 0 )) != -1 ) {
		//cout<<"Work tmp dir of vertex files exists\n";

	}else{
		cout<<"Work tmp dir of vertex files does not exist\n";
		exit(0);
	}
	int file_count;
    char files[3][100];
	char *delim = "_";
	char * pch;
	FILE *bmpFile;
	int bmp_size;
	char realfilelocation[200];
	char tmp[50];
	unsigned char *bmpbuf;

	// read color and write -------
	strcpy(realfilelocation,work_dir);
	strcat(realfilelocation,"\\");
   	strcat(realfilelocation, "TER_");
  	strcat (realfilelocation, shFileName);
	strcat(realfilelocation,"_COLOR_.BMP");
	if((bmpFile=fopen(realfilelocation,"rb"))==NULL){
		cout<<"bmp color File, ("<<realfilelocation<<") open error !\n";
		exit(0);
	}
	bmp_size=filelength(fileno(bmpFile));
	bmpbuf=new unsigned char[bmp_size];
    fread(bmpbuf,1,bmp_size,bmpFile);
	fclose(bmpFile);
	if(size==199829){//196KB:APA,BAL,CUB,GRE,IRA,LFA,NSK,PGU,SPA,WTA
		for(int i=1078;i<66614;i++){
			shbuf[(149+((i-1078)*3))]=bmpbuf[i];
		}
    }else if(size==126899){//124KB:EGY,FRA,VLA

	}else if(size==122024){//119KB:TVIET, (color, type, hight)

    }else{           
    	cout<<"Unknow size of terrien file\n";
    	exit(0);
    }

	// read type and write -------
	strcpy(realfilelocation,work_dir);
	strcat(realfilelocation,"\\");
   	strcat(realfilelocation, "TER_");
  	strcat (realfilelocation, shFileName);
	strcat(realfilelocation,"_TYPE_.BMP");
	if((bmpFile=fopen(realfilelocation,"rb"))==NULL){
		cout<<"bmp color File, ("<<realfilelocation<<") open error !\n";
		exit(0);
	}
	bmp_size=filelength(fileno(bmpFile));
	bmpbuf=new unsigned char[bmp_size];
    fread(bmpbuf,1,bmp_size,bmpFile);
	fclose(bmpFile);
	if(size==199829){//196KB:APA,BAL,CUB,GRE,IRA,LFA,NSK,PGU,SPA,WTA
		for(int i=1078;i<66614;i++){
			shbuf[(150+((i-1078)*3))]=bmpbuf[i];
		}
    }else if(size==126899){//124KB:EGY,FRA,VLA

	}else if(size==122024){//119KB:TVIET, (color, type, hight)

    }else{           
    	cout<<"Unknow size of terrien file\n";
    	exit(0);
    }
	// read height and write -------
	strcpy(realfilelocation,work_dir);
	strcat(realfilelocation,"\\");
   	strcat(realfilelocation, "TER_");
  	strcat (realfilelocation, shFileName);
	strcat(realfilelocation,"_HEIGHT_.BMP");
	if((bmpFile=fopen(realfilelocation,"rb"))==NULL){
		cout<<"bmp color File, ("<<realfilelocation<<") open error !\n";
		exit(0);
	}
	bmp_size=filelength(fileno(bmpFile));
	bmpbuf=new unsigned char[bmp_size];
    fread(bmpbuf,1,bmp_size,bmpFile);
	fclose(bmpFile);
	if(size==199829){//196KB:APA,BAL,CUB,GRE,IRA,LFA,NSK,PGU,SPA,WTA
		for(int i=1078;i<66614;i++){
			shbuf[(151+((i-1078)*3))]=bmpbuf[i];
		}
    }else if(size==126899){//124KB:EGY,FRA,VLA

	}else if(size==122024){//119KB:TVIET, (color, type, hight)

    }else{           
    	cout<<"Unknow size of terrien file\n";
    	exit(0);
    }	
	
	if((shFile=fopen(shFileName,"wb"))==NULL){
		cout<<"sh File, ("<<shFileName<<") open for wrinting error !\n";
		exit(0);

	}	
    fwrite(shbuf,1,size,shFile); // write Class File
	fclose(shFile);				// Close Class File
    

}
//---------------------------------------

void square_flat(int longitude, int latitude, int side, int height, unsigned char *shbuf){ // make a square flat
        //change longitude, latitude to x,y
        int i,j=0;
        int side2=(int)side/2;
        int y = (int)longitude/8192; //13 for Test
        int x = (int)latitude/8192;  //130 for Test

        for(i=x-side2;i<x+side2;i++){
            for(j=y-side2;j<y+side2;j++){
                //cout<<((i*256)+j)<<"\n";
                if(i<0 || i>255 || j<0 || j>255){
                       // touch map's board, igore
                }else{
                      shbuf[(151+(((i*256)+j)*3))] = height; 
                }
            }        
        }
}

void square_flat_xy(int x, int y, int side, int height, unsigned char *shbuf){ // make a square flat

        int i,j=0;
        int side2=(int)side/2;

        for(i=x-side2;i<x+side2;i++){
            for(j=y-side2;j<y+side2;j++){
                //cout<<((i*256)+j)<<"\n";
                if(i<0 || i>255 || j<0 || j>255){
                       // touch map's board, igore
                }else{
                      shbuf[(151+(((i*256)+j)*3))] = height; 
                }
            }        
        }
}

//---------------------------------------

int make(int random_height_input){
    int random_height=0;
    random_height=random_height_input;

    
    srand(time(NULL));
	
    char work_dir[50];
	int size;
	// load original sh file
	if((shFile=fopen(shFileName,"rb"))==NULL){
		cout<<"sh File, ("<<shFileName<<") open error !\n";
		exit(0);

	}
	
	size=filelength(fileno(shFile));
	shbuf=new unsigned char[size];
    fread(shbuf,1,size,shFile); // Read Class File
	fclose(shFile);				// Close Class File
	
	// load 3 bmp files

	work_dir[0]='\0';
    strcpy (work_dir, "tmp_");
    strcat (work_dir, shFileName);
    
    if( (_access( work_dir, 0 )) != -1 ) {
		//cout<<"Work tmp dir of vertex files exists\n";

	}else{
		cout<<"Work tmp dir of vertex files does not exist\n";
		exit(0);
	}
	int file_count;
    char files[3][100];
	char *delim = "_";
	char * pch;
	FILE *bmpFile;
	FILE *mmFile; // *.MM File
	int bmp_size;
	char realfilelocation[200];
	char tmp[50];
	unsigned char *bmpbuf;
	unsigned char *bmpbuf_color;
	unsigned char *bmpbuf_height;
	unsigned char *bmpbuf_type;
   
    
    // load original MM (Map object) file
	int MMFileHandle;
    FILE *MMFile;
    char *MMFileName;
    int MMsize=0;
    unsigned char *MMbuf;
    char MMrealfilelocation[200];
    MMrealfilelocation[0]='\0';
    int MMXY[500][2];
    int MMXY_cnt=0;
    
	//strcpy(MMrealfilelocation,work_dir);
	//strcat(MMrealfilelocation,"\\");
  	strcat(MMrealfilelocation, shFileName);
  	MMrealfilelocation[4]='M';
  	MMrealfilelocation[5]='M';
  	MMrealfilelocation[6]='\0';

	//cout<<MMrealfilelocation;
	
	ifstream MMfile (MMrealfilelocation);
	string line;
	string back_line1="";
	string back_line2="";
	int mm_sub_cnt=0;
    if (MMfile.is_open()){
        while ( getline (MMfile,line) ){
              //cout << line << '\n';
             	if(line[1]=='p' && line[2]=='o' && line[3]=='s' ){
                   	if(back_line2[0]=='o' && back_line2[1]=='b' && back_line2[2]=='j' ){
                        // get all obj XY address
                        //cout << line << '\n';
                        istringstream iss(line);
                            do{
                                string sub;
                                iss >> sub;
                                if(mm_sub_cnt==1){
                                    //cout << "Substring: " << sub << endl;
                                    MMXY[MMXY_cnt][0]= stoi(sub);
                                }
                                if(mm_sub_cnt==3){
                                    //cout << "Substring: " << sub << endl;
                                    MMXY[MMXY_cnt][1]= stoi(sub);
                                }
                                mm_sub_cnt++;
                            } while (iss);
                            mm_sub_cnt=0;
                            MMXY_cnt++;
                    }else{
                    }
                }else{
                }
                back_line2=back_line1;
                back_line1=line;
        }
        MMfile.close();
    }else{
          cout << "\nUnable to open MM file"; 
          exit(0);
    }

	//if((MMFile=fopen(MMrealfilelocation,"rt"))==NULL){
	//	cout<<"MM File, ("<<MMrealfilelocation<<") open error !\n";
	//	exit(0);
	//}	
	
	
    // try to load MAP BMP (256x256) file
    FILE *bmpMAPFile;
    int bmpMAP_size=0;
    unsigned char *bmpbuf_MAP;
   	MMrealfilelocation[4]='B';
  	MMrealfilelocation[5]='M';
  	MMrealfilelocation[6]='P';
  	MMrealfilelocation[7]='\0';
  	
  	//cout<<MMrealfilelocation<<"\n";
	if((bmpMAPFile=fopen(MMrealfilelocation,"rb"))==NULL){
		cout<<"No MAP BMP File support, ("<<MMrealfilelocation<<") open error !\n";		
		cout<<"if the BMP MAP is existed, please resize it to 256x256!\n";		
	}else{
        
        bmpMAP_size=filelength(fileno(bmpMAPFile));
       	bmpbuf_MAP=new unsigned char[bmpMAP_size];
        fread(bmpbuf_MAP,1,bmpMAP_size,bmpMAPFile);
        if(bmpMAP_size==66614){
            //cout<<"MAP BMP File support to draw the rivers, roads and cities.\n";
        }
    }
    

	// read color and write -------
	strcpy(realfilelocation,work_dir);
	strcat(realfilelocation,"\\");
   	strcat(realfilelocation, "TER_");
  	strcat (realfilelocation, shFileName);
	strcat(realfilelocation,"_COLOR_.BMP");
	if((bmpFile=fopen(realfilelocation,"rb"))==NULL){
		cout<<"bmp color File, ("<<realfilelocation<<") open error !\n";
		exit(0);
	}
	bmp_size=filelength(fileno(bmpFile));
	//bmpbuf=new unsigned char[bmp_size];
	bmpbuf_color=new unsigned char[bmp_size];
    fread(bmpbuf_color,1,bmp_size,bmpFile);
	fclose(bmpFile);
	if(size==199829){//196KB:APA,BAL,CUB,GRE,IRA,LFA,NSK,PGU,SPA,WTA
		for(int i=1078;i<66614;i++){
			shbuf[(149+((i-1078)*3))]=bmpbuf_color[i];
		}
    }else if(size==126899){//124KB:EGY,FRA,VLA

	}else if(size==122024){//119KB:TVIET, (color, type, hight)

    }else{           
    	cout<<"Unknow size of terrien file\n";
    	exit(0);
    }

	// read type and write -------
	strcpy(realfilelocation,work_dir);
	strcat(realfilelocation,"\\");
   	strcat(realfilelocation, "TER_");
  	strcat (realfilelocation, shFileName);
	strcat(realfilelocation,"_TYPE_.BMP");
	if((bmpFile=fopen(realfilelocation,"rb"))==NULL){
		cout<<"bmp color File, ("<<realfilelocation<<") open error !\n";
		exit(0);
	}
	bmp_size=filelength(fileno(bmpFile));
	bmpbuf_type=new unsigned char[bmp_size];
    fread(bmpbuf_type,1,bmp_size,bmpFile);
	fclose(bmpFile);
	if(size==199829){//196KB:APA,BAL,CUB,GRE,IRA,LFA,NSK,PGU,SPA,WTA
		for(int i=1078;i<66614;i++){
			shbuf[(150+((i-1078)*3))]=bmpbuf_type[i];
		}
    }else if(size==126899){//124KB:EGY,FRA,VLA

	}else if(size==122024){//119KB:TVIET, (color, type, hight)

    }else{           
    	cout<<"Unknow size of terrien file\n";
    	exit(0);
    }
	// read height and write -------
	strcpy(realfilelocation,work_dir);
	strcat(realfilelocation,"\\");
   	strcat(realfilelocation, "TER_");
  	strcat (realfilelocation, shFileName);
	strcat(realfilelocation,"_HEIGHT_.BMP");
	if((bmpFile=fopen(realfilelocation,"rb"))==NULL){
		cout<<"bmp color File, ("<<realfilelocation<<") open error !\n";
		exit(0);
	}
	bmp_size=filelength(fileno(bmpFile));
	bmpbuf_height=new unsigned char[bmp_size];
    fread(bmpbuf_height,1,bmp_size,bmpFile);
	fclose(bmpFile);
	int pre_h=0, now_h=0;
	if(size==199829){//196KB:APA,BAL,CUB,GRE,IRA,LFA,NSK,PGU,SPA,WTA
		for(int i=1078;i<66614;i++){
// ---------------------------------------------------------------------------------------
// ---------------------------make random height here (2015.03)---------------------------
// ---------------------------------------------------------------------------------------
//                        shbuf[(151+((i-1078)*3))]=randnum(1,70);
                        shbuf[(151+((i-1078)*3))]=randnum(1,random_height);
                        
                        
         /*
        //This section is a attemp to let each near point have similar attitude
        //(2016.05)           
                     //shbuf[(151+((i-1078)*3))]=randnum(1,random_height);
                     do{
                        now_h=randnum(1,random_height);  
                     }while(abs(now_h-pre_h)>2);
                        shbuf[(151+((i-1078)*3))]=now_h;
                        pre_h=now_h;
                        //printf("%d,%d\n", i, shbuf[(151+((i-1078)*3))]);
                        //shbuf[(151+((i-1078)*3))] = randnum(1,random_height);  
         */              
                        
		}
// ---------------------------make some random flat spot here (2015.04)-------------------
        for(int x=0;x<100;x++){ // pick some spot to flat
                //int flat_spot = randnum(1079,66613);
                int flat_spot = 1078+randnum(0,32767)+randnum(0,32767); // Due to rand_MAX =32767
                //cout<<flat_spot<<"\n";
                square_flat_xy((flat_spot-1078)/256,((flat_spot-1078)-(256*((flat_spot-1078)/256))), 4, randnum(1,random_height+5), shbuf);        
        }
        
// ---------------------------make river, road and city flat here (2015.04)-------------------        
 		for(int i=1078;i<66614;i++){
            // make river, road and city flat here
            // Each MAP has different color index for river/road and city
            // BAL
            if(MMrealfilelocation[0]=='B' && MMrealfilelocation[1]=='A' && MMrealfilelocation[2]=='L'){
                if(bmpbuf_MAP[i]>=7 && (int)bmpbuf_MAP[i] <=12){
                      shbuf[(151+((i-1078)*3))]=0; //make river
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==108 || (int)bmpbuf_MAP[i]==125){
                      shbuf[(151+((i-1078)*3))]=0; //make road
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 4, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==97 || (int)bmpbuf_MAP[i]==102){
                      shbuf[(151+((i-1078)*3))]=0; //make city
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
            }
            // APA
            if(MMrealfilelocation[0]=='A' && MMrealfilelocation[1]=='P' && MMrealfilelocation[2]=='A'){
                if(bmpbuf_MAP[i]==4){
                      shbuf[(151+((i-1078)*3))]=0; //make river
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==79){
                      shbuf[(151+((i-1078)*3))]=0; //make road
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 4, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==1){
                      shbuf[(151+((i-1078)*3))]=0; //make city
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
            }
            // CUB
            if(MMrealfilelocation[0]=='C' && MMrealfilelocation[1]=='U' && MMrealfilelocation[2]=='B'){
                if(bmpbuf_MAP[i]==3){
                      shbuf[(151+((i-1078)*3))]=0; //make river
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==87 || bmpbuf_MAP[i]==77 || bmpbuf_MAP[i]==68){
                      shbuf[(151+((i-1078)*3))]=0; //make road
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 4, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==1){
                      shbuf[(151+((i-1078)*3))]=0; //make city
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
            }
            // GRE
            if(MMrealfilelocation[0]=='G' && MMrealfilelocation[1]=='R' && MMrealfilelocation[2]=='E'){
                if(bmpbuf_MAP[i]==108 || bmpbuf_MAP[i]==109){
                      shbuf[(151+((i-1078)*3))]=0; //make river
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==4 || bmpbuf_MAP[i]==8 || bmpbuf_MAP[i]==11 || bmpbuf_MAP[i]==13){
                      shbuf[(151+((i-1078)*3))]=0; //make road
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 4, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==32){
                      shbuf[(151+((i-1078)*3))]=0; //make city
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
            }
            // IRA
            if(MMrealfilelocation[0]=='I' && MMrealfilelocation[1]=='R' && MMrealfilelocation[2]=='A'){
                if(bmpbuf_MAP[i]==99){
                      shbuf[(151+((i-1078)*3))]=0; //make river
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==10 || bmpbuf_MAP[i]==11 || bmpbuf_MAP[i]==12 || bmpbuf_MAP[i]==20 || bmpbuf_MAP[i]==24){
                      shbuf[(151+((i-1078)*3))]=0; //make road
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 4, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==95){
                      shbuf[(151+((i-1078)*3))]=0; //make city
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
            }
            // LFA
            if(MMrealfilelocation[0]=='L' && MMrealfilelocation[1]=='F' && MMrealfilelocation[2]=='A'){
                if(bmpbuf_MAP[i]==1){
                      shbuf[(151+((i-1078)*3))]=0; //make city
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
            }
/*
           // NSK
            if(MMrealfilelocation[0]=='N' && MMrealfilelocation[1]=='S' && MMrealfilelocation[2]=='K'){
                 if(bmpbuf_MAP[i]==29){
                      shbuf[(151+((i-1078)*3))]=0; //make river
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
            
                if(bmpbuf_MAP[i]==102 || bmpbuf_MAP[i]==109){
                      shbuf[(151+((i-1078)*3))]=0; //make road
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shoreP
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 4, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==1){
                      shbuf[(151+((i-1078)*3))]=0; //make city
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
           
            }
*/
           // PGU
            if(MMrealfilelocation[0]=='P' && MMrealfilelocation[1]=='G' && MMrealfilelocation[2]=='U'){
                if(bmpbuf_MAP[i]==89){
                      shbuf[(151+((i-1078)*3))]=0; //make river
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==2){
                      shbuf[(151+((i-1078)*3))]=0; //make city
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
            }
           // SPA
            if(MMrealfilelocation[0]=='S' && MMrealfilelocation[1]=='P' && MMrealfilelocation[2]=='A'){
                if(bmpbuf_MAP[i]==67){
                      shbuf[(151+((i-1078)*3))]=0; //make river
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==122 || bmpbuf_MAP[i]==119 || bmpbuf_MAP[i]==102){
                      shbuf[(151+((i-1078)*3))]=0; //make road
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 4, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==1){
                      shbuf[(151+((i-1078)*3))]=0; //make city
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      // make shore
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
            }

           // WTA
            if(MMrealfilelocation[0]=='W' && MMrealfilelocation[1]=='T' && MMrealfilelocation[2]=='A'){
                if(bmpbuf_MAP[i]==110){
                      shbuf[(151+((i-1078)*3))]=0; //make river
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==2 || bmpbuf_MAP[i]==4 || bmpbuf_MAP[i]==5 || bmpbuf_MAP[i]==6 || bmpbuf_MAP[i]==9 || bmpbuf_MAP[i]==8 || bmpbuf_MAP[i]==18 || bmpbuf_MAP[i]==11 || bmpbuf_MAP[i]==15){
                      shbuf[(151+((i-1078)*3))]=0; //make road
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 4, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
                if(bmpbuf_MAP[i]==29){
                      shbuf[(151+((i-1078)*3))]=0; //make city
                      //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                      square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 3, 0, shbuf);
                      // The last second operand means the area of the flat spot
                }
            }
		} 
// ---------------------------make sea and shores here (2015.04)-------------------             
		for(int i=1078;i<66614;i++){
            // make sea and shore flat here
            if(bmpbuf_color[i] == 255){
                  shbuf[(151+((i-1078)*3))]=0; //make sea
                  //cout<<"["<<i<<"]"<<(i-1078)/256<<","<<((i-1078)-(256*((i-1078)/256)))<<"\n";
                  // make shore
                  square_flat_xy((i-1078)/256,((i-1078)-(256*((i-1078)/256))), 8, 0, shbuf);
                  // The last second operand means the area of the flat spot
            }
		}
		
		// make flat on each obj
		//square_flat(109608, 1069032, 8, 0, shbuf); //
		//
	    for(int k=0;k<MMXY_cnt;k++){
            //cout<<MMXY[k][0]<<","<<MMXY[k][1]<<"\n";
            // make each obj location flat (20150407), make each obj location not only flat 0 but some attitude
// ---------------------------------------------------------------------------------------
            square_flat(MMXY[k][0], MMXY[k][1], 10, 0, shbuf); // this is make MM obj flat
            //square_flat(MMXY[k][0], MMXY[k][1], 10, randnum(0,10), shbuf); // this is make MM obj as a random height (0~10)
            // 2016/05
// ---------------------------------------------------------------------------------------
            // The last second operand means the area of the flat spot
            
        }		
		// --------------------------
    }else if(size==126899){//124KB:EGY,FRA,VLA

	}else if(size==122024){//119KB:TVIET, (color, type, hight)

    }else{           
    	cout<<"Unknow size of terrien file\n";
    	exit(0);
    }	
	
	if((shFile=fopen(shFileName,"wb"))==NULL){
		cout<<"sh File, ("<<shFileName<<") open for wrinting error !\n";
		exit(0);

	}	
    fwrite(shbuf,1,size,shFile); // write Class File
	fclose(shFile);				// Close Class File
    

}




//---------------------------------------

int main(int arguments_count,char *arguments[]){
	
    if(arguments_count < 3){
		cout<<"Usage: faMap2 <options> <*.T2> <random height(optional)>..."<<"\n\n";
		cout<<"ex : faMap2 e BAL.T2 means extract BAL.T2 to \\BAL.T2"<<"\n";
		cout<<"     faMap2 b BAL.T2 means build BAL.T2 based on the info of \\BAL.T2"<<"\n";		
		cout<<"     faMap2 m BAL.T2 means random make BAL.T2 (require BAL.MM)"<<"\n";
		cout<<"     make could have another option, random height"<<"\n";
		cout<<"     faMap2 m BAL.T2 30, here 30 means a random height. "<<"\n";
		cout<<"     without random height assigned, the random height is 70 "<<"\n";
		exit(0);	
    }
    else{
		op=arguments[1];
		shFileName = arguments[2];		
	}
	if(op[0]=='e'){
	// eXtract a T2 file into 3 BMP
		ext();	
	}else if (op[0]=='b'){
	// Build 3 bmp file into T2
		build();
	}else if (op[0]=='m'){
	// Make a T2 based on random method, and then ext to check
        //if the random height value is assigned
        if(arguments[3]!=NULL){
        	ext();
    		make(atoi(arguments[3]));
    		ext();
        }else{
        	ext();
    		make(60);
    		ext();
        }
	}else{
		cout<<"Wrong op.\n";
		exit(0);
	}

 return 0;   
}
	
	
