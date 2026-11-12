//
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

struct face_st {
    int face_id;
    int vertex_count;
	int vp[10];
};

face_st face_index[50][500];
int face_count[50];
FILE *vexFile[50];
FILE *edgFile[50];


//ofstream log("Log.TXT");


//---------------------------------------

void hexprint(unsigned char i){
    if(i <= 0xF){
         printf("0%x ",i);
    }else{
         printf("%x ",i);
    }

}


//---------------------------------------

int hex2xyz(unsigned char c1, unsigned char c2){
	int result=0;
	if(int(c2)>=128){
		result=((int(c2)-255)*256+(int(c1)-255))-1;
	
	}else{
		result=int(c2)*256+int(c1);
	
	}	
	return result;
}

//---------------------------------------
int preexam(int loc_cod, int size){
	int result=0;
	int p;
	for(int j=0;j<size;j++){
		for(int k=0;k<6;k=k+2){
			p=hex2xyz(shbuf[(loc_cod+6)+j*6+k], shbuf[(loc_cod+6)+j*6+k+1]);
			if (p>10000 || p<-10000){
				return 0;
			}
		}
	}
	return 1;
}

//-----------------------------------
int xyz2hex(char *line, int location){
	char * pch;
	char cx[10];
	char cy[10];
	char cz[10];
	int x,y,z,tmp;
	unsigned char c[6];
	
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

	//------
	if(x==-1){
		c[0]=0xff;
		c[1]=0xff;		
	}else if(x<0){
		if(x<-255){			
			tmp=abs(x)/255;
			c[1]=255-tmp;
			c[0]=256+x+(tmp*256);
		}else{
			c[0]=256+x;
			c[1]=0xff;
		}		
	}else if(x==0){
		c[0]=0x00;
		c[1]=0x00;

	}else{
		if(x>256){
			tmp=x/255;
			c[1]=tmp;
			c[0]=x-(tmp*256);			
		}else{
			c[0]=x;
			c[1]=0x00;
		}
	}

	//------
	if(y==-1){
		c[2]=0xff;
		c[3]=0xff;		
	}else if(y<0){
		if(y<-255){
			tmp=abs(y)/255;
			c[3]=255-tmp;
			c[2]=256+y+(tmp*256);
		}else{
			c[2]=256+y;
			c[3]=0xff;
		}		
	}else if(y==0){
		c[2]=0x00;
		c[3]=0x00;	
	}else{
		if(y>256){
			tmp=y/255;
			c[3]=tmp;
			c[2]=y-(tmp*256);			
		}else{
			c[2]=y;
			c[3]=0x00;
		}
	}
	//------
	if(z==-1){
		c[4]=0xff;
		c[5]=0xff;		
	}else if(z<0){
		if(z<-255){
			tmp=abs(z)/255;
			c[5]=255-tmp;
			c[4]=256+z+(tmp*256);
		}else{
			c[4]=256+z;
			c[5]=0xff;
		}		
	}else if(z==0){
		c[4]=0x00;
		c[5]=0x00;	
	}else{
		if(z>256){
			tmp=z/255;
			c[5]=tmp;
			c[4]=z-(tmp*256);			
		}else{
			c[4]=z;
			c[5]=0x00;
		}
	}
	
	// put into shbuf
	for(int i=0;i<6;i++){
		shbuf[location+i]=c[i];	
	}	
	return 0;
}

//---------------------------------------

int lookingFC(int offset){
	// find next 60 byte for vaild FCxx initial
	int flag =0;
	for(i=1;i<61;i++){
		if(shbuf[offset+i]==0xFC){
			if(shbuf[offset+i+1]==0x41){
				flag=65;
			}else if(shbuf[offset+i+1]==0x61){
				//cout<<"found next 61:"<<offset+i+1<<"\n";
				flag=97;
			}else if(shbuf[offset+i+1]==0x63){
				//cout<<"found next 63:"<<offset+i+1<<"\n";
				flag=99;
			}else if(shbuf[offset+i+1]==0x44){		
				//cout<<"found next 44:"<<offset+i+1<<"\n";
				flag=68;
			}else if(shbuf[offset+i+1]==0x64){		
				//cout<<"found next 64:"<<offset+i+1<<"\n";
				flag=100;
			}else if(shbuf[offset+i+1]==0xEE){		
				//cout<<"found next EE:"<<offset+i+1<<"\n";
				flag=238;
			}else if(shbuf[offset+i+1]==0xED){		
				//cout<<"found next ED:"<<offset+i+1<<"\n";
				flag=237;
			}else if(shbuf[offset+i+1]==0x6C){
				//cout<<"found next 6C:"<<offset+i+1<<"\n";
				flag=108;
			}else if(shbuf[offset+i+1]==0x4C){
				//cout<<"found next 4C:"<<offset+i+1<<"\n";
				flag=76;
			}
		}
		if(flag>0){
			return i;
		}
	}
	return -1;
	
}
//---------------------------------------
int sumvex(int current_vex){
    // last 2 words is 00 00 of 82 structure, and larger than 25, should be another LOD
    if(shbuf[loc_cod[current_vex]+4] == 0x00 && shbuf[loc_cod[current_vex]+5] == 0x00){
        if(size_cod[current_vex]>16){
            return 0;        
        }
    }

	int sum=0;
		for(int i=0;i<current_vex;i++){
			sum=sum+size_cod[i];
		}

	return sum;
}

//---------------------------------------

int findPN(int start, int end, int current_vex, int face_id, int face_count, int max_p_count, int ext_way){
	int flag =0;
	int location=0;
	// find correct postion of numbers of vertex points in a FC block
	// step 1: move 1E at tail
	if(shbuf[end]==0x1E && shbuf[end-1]==0x1E && shbuf[end-2]==0x1E){
		end=end-3;
	}else if(shbuf[end]==0x1E && shbuf[end-1]==0x1E){
		end=end-2;
	}else if(shbuf[end]==0x1E){
		end=end-1;
	}
	
	face_index[current_vex][face_count].vertex_count=0;
	face_index[current_vex][face_count].face_id=face_id;
	
	
	if(ext_way==0){ // do newer way to extract
	// step 1.1: point number at 15th
	if(face_id==68 || face_id==237 || face_id==238 || face_id==97 || face_id==108 || face_id==254 || face_id==115 || face_id==253){
	// FC 44(68), FC ED(237), FC EE(238), FC 61(97), FC 6C(108), FC FE(254), FC 73(115), FC FD(253)
	// FC 4C(76) is not enable
//	if(face_id==76 || face_id==68 || face_id==237 || face_id==238 || face_id==97 || face_id==108 || face_id==254 || face_id==115 || face_id==253){
			int single=0;
			location=start+15-1;//double digit
			face_index[current_vex][face_count].vertex_count=int(shbuf[start+15-1]);
			for(int h=0;h<face_index[current_vex][face_count].vertex_count;h++){				
				face_index[current_vex][face_count].vp[h]=int(shbuf[start+15-1+1+h*2])+256*int(shbuf[start+15-1+1+h*2+1])-sumvex(current_vex);
			}
			for(int h=0;h<face_index[current_vex][face_count].vertex_count;h++){
				if (face_index[current_vex][face_count].vp[h]>size_cod[current_vex]){//single digit
					single=1;
				}
			}
			if(single==1){
				for(int h=0;h<face_index[current_vex][face_count].vertex_count;h++){
					face_index[current_vex][face_count].vp[h]=int(shbuf[start+15-1+1+h])-sumvex(current_vex);
				}
			}
			
			
		for(int h=0;h<face_index[current_vex][face_count].vertex_count;h++){
				if(face_index[current_vex][face_count].vp[h]<0){
					face_index[current_vex][face_count].vertex_count=0;
				}
		}
	
		cout<<"("<<face_index[current_vex][face_count].vertex_count<<" ";
		for(int nn=0;nn<face_index[current_vex][face_count].vertex_count;nn++){
			cout<<","<<face_index[current_vex][face_count].vp[nn];
		}
		cout<<")   ";
		return location;

	}
	}
/*
	// step 1.3: FC 4C number at 15th or 
	if(face_id==76){//FC 4C

	}
*/



	
	// step 2: maybe 3 points, so 3 bytes or 6 bytes
	if(shbuf[end-3]==0x03){
		// 3x1 points
		location=end-3;
		cout<<"(1,";hexprint(shbuf[end-3]);cout<<") ";
		face_index[current_vex][face_count].vertex_count=3;
		face_index[current_vex][face_count].vp[0]=int(shbuf[end-2])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[1]=int(shbuf[end-1])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[2]=int(shbuf[end-0])-sumvex(current_vex);
		if(face_index[current_vex][face_count].vp[0]>max_p_count || face_index[current_vex][face_count].vp[1]>max_p_count || face_index[current_vex][face_count].vp[2]>max_p_count){
			cout<<"Wrong vp parsing, larger than "<< max_p_count<<"\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		if(face_index[current_vex][face_count].vp[0]<0 || face_index[current_vex][face_count].vp[1]<0 || face_index[current_vex][face_count].vp[2]<0){
			cout<<"Wrong vp parsing, minus value\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		cout<<"("<<face_index[current_vex][face_count].vp[0]<<","<<face_index[current_vex][face_count].vp[1]<<","<<face_index[current_vex][face_count].vp[2]<<") ";

	}
	if(shbuf[end-6]==0x03){
		//3x2 points
		location=end-6;
		cout<<"(2,";hexprint(shbuf[end-6]);cout<<") ";
		face_index[current_vex][face_count].vertex_count=3;
		face_index[current_vex][face_count].vp[0]=int(shbuf[end-5])+int(shbuf[end-4])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[1]=int(shbuf[end-3])+int(shbuf[end-2])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[2]=int(shbuf[end-1])+int(shbuf[end-0])*256-sumvex(current_vex);
		if(face_index[current_vex][face_count].vp[0]>max_p_count || face_index[current_vex][face_count].vp[1]>max_p_count || face_index[current_vex][face_count].vp[2]>max_p_count){
			cout<<"Wrong vp parsing, larger than "<< max_p_count<<"\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		if(face_index[current_vex][face_count].vp[0]<0 || face_index[current_vex][face_count].vp[1]<0 || face_index[current_vex][face_count].vp[2]<0){
			cout<<"Wrong vp parsing, minus value\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		cout<<"("<<face_index[current_vex][face_count].vp[0]<<","<<face_index[current_vex][face_count].vp[1]<<","<<face_index[current_vex][face_count].vp[2]<<")  ";

	}
	
	// step 3: maybe 4 points, so 4 bytes or 8 bytes
	if(shbuf[end-4]==0x04){
		// 4x1 points
		location=end-4;
		cout<<"(1,";hexprint(shbuf[end-4]);cout<<") ";
		face_index[current_vex][face_count].vertex_count=4;
		face_index[current_vex][face_count].vp[0]=int(shbuf[end-3])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[1]=int(shbuf[end-2])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[2]=int(shbuf[end-1])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[3]=int(shbuf[end-0])-sumvex(current_vex);
		if(face_index[current_vex][face_count].vp[0]>max_p_count || face_index[current_vex][face_count].vp[1]>max_p_count || face_index[current_vex][face_count].vp[2]>max_p_count || face_index[current_vex][face_count].vp[3]>max_p_count){
			cout<<"Wrong vp parsing, larger than "<< max_p_count<<"\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		if(face_index[current_vex][face_count].vp[0]<0 || face_index[current_vex][face_count].vp[1]<0 || face_index[current_vex][face_count].vp[2]<0 || face_index[current_vex][face_count].vp[3]<0){
			cout<<"Wrong vp parsing, minus value\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		cout<<"("<<face_index[current_vex][face_count].vp[0]<<","<<face_index[current_vex][face_count].vp[1]<<","<<face_index[current_vex][face_count].vp[2]<<","<<face_index[current_vex][face_count].vp[3]<<")  ";
	}
	else if(shbuf[end-8]==0x04){
		//4x2 points
		location=end-8;
		cout<<"(2,";hexprint(shbuf[end-8]);cout<<") ";
		face_index[current_vex][face_count].vertex_count=4;
		face_index[current_vex][face_count].vp[0]=int(shbuf[end-7])+int(shbuf[end-6])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[1]=int(shbuf[end-5])+int(shbuf[end-4])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[2]=int(shbuf[end-3])+int(shbuf[end-2])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[3]=int(shbuf[end-1])+int(shbuf[end-0])*256-sumvex(current_vex);
		if(face_index[current_vex][face_count].vp[0]>max_p_count || face_index[current_vex][face_count].vp[1]>max_p_count || face_index[current_vex][face_count].vp[2]>max_p_count || face_index[current_vex][face_count].vp[3]>max_p_count){
			cout<<"Wrong vp parsing, larger than "<< max_p_count<<"\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		if(face_index[current_vex][face_count].vp[0]<0 || face_index[current_vex][face_count].vp[1]<0 || face_index[current_vex][face_count].vp[2]<0 || face_index[current_vex][face_count].vp[3]<0){
			cout<<"Wrong vp parsing, minus value\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		cout<<"("<<face_index[current_vex][face_count].vp[0]<<","<<face_index[current_vex][face_count].vp[1]<<","<<face_index[current_vex][face_count].vp[2]<<","<<face_index[current_vex][face_count].vp[3]<<")  ";
	}
	
	// step 4: maybe 5 points, so 5 bytes or 10 bytes
	else if(shbuf[end-5]==0x05){
		// 5x1 points
		location=end-5;
		cout<<"(1,";hexprint(shbuf[end-5]);cout<<") ";
		face_index[current_vex][face_count].vertex_count=5;
		face_index[current_vex][face_count].vp[0]=int(shbuf[end-4])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[1]=int(shbuf[end-3])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[2]=int(shbuf[end-2])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[3]=int(shbuf[end-1])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[4]=int(shbuf[end-0])-sumvex(current_vex);
		if(face_index[current_vex][face_count].vp[0]>max_p_count || face_index[current_vex][face_count].vp[1]>max_p_count || face_index[current_vex][face_count].vp[2]>max_p_count || face_index[current_vex][face_count].vp[3]>max_p_count || face_index[current_vex][face_count].vp[4]>max_p_count){
			cout<<"Wrong vp parsing, larger than "<< max_p_count<<"\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		if(face_index[current_vex][face_count].vp[0]<0 || face_index[current_vex][face_count].vp[1]<0 || face_index[current_vex][face_count].vp[2]<0 || face_index[current_vex][face_count].vp[3]<0 || face_index[current_vex][face_count].vp[4]<0){
			cout<<"Wrong vp parsing, minus value\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		cout<<"("<<face_index[current_vex][face_count].vp[0]<<","<<face_index[current_vex][face_count].vp[1]<<","<<face_index[current_vex][face_count].vp[2]<<","<<face_index[current_vex][face_count].vp[3]<<","<<face_index[current_vex][face_count].vp[4]<<")  ";
	}
	else if(shbuf[end-10]==0x05){
		//5x2 points
		location=end-10;
		cout<<"(2,";hexprint(shbuf[end-10]);cout<<") ";
		face_index[current_vex][face_count].vertex_count=5;
		face_index[current_vex][face_count].vp[0]=int(shbuf[end-9])+int(shbuf[end-8])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[1]=int(shbuf[end-7])+int(shbuf[end-6])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[2]=int(shbuf[end-5])+int(shbuf[end-4])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[3]=int(shbuf[end-3])+int(shbuf[end-2])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[4]=int(shbuf[end-1])+int(shbuf[end-0])*256-sumvex(current_vex);
		if(face_index[current_vex][face_count].vp[0]>max_p_count || face_index[current_vex][face_count].vp[1]>max_p_count || face_index[current_vex][face_count].vp[2]>max_p_count || face_index[current_vex][face_count].vp[3]>max_p_count || face_index[current_vex][face_count].vp[4]>max_p_count){
			cout<<"Wrong vp parsing, larger than "<< max_p_count<<"\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		if(face_index[current_vex][face_count].vp[0]<0 || face_index[current_vex][face_count].vp[1]<0 || face_index[current_vex][face_count].vp[2]<0 || face_index[current_vex][face_count].vp[3]<0 || face_index[current_vex][face_count].vp[4]<0){
			cout<<"Wrong vp parsing, minus value\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		cout<<"("<<face_index[current_vex][face_count].vp[0]<<","<<face_index[current_vex][face_count].vp[1]<<","<<face_index[current_vex][face_count].vp[2]<<","<<face_index[current_vex][face_count].vp[3]<<","<<face_index[current_vex][face_count].vp[4]<<")  ";
	}
	
	// step 5: maybe 6 points, so 6 bytes or 12 bytes
	else if(shbuf[end-6]==0x06){
		// 6x1 points
		location=end-6;
		cout<<"(1,";hexprint(shbuf[end-6]);cout<<") ";
		face_index[current_vex][face_count].vertex_count=6;
		face_index[current_vex][face_count].vp[0]=int(shbuf[end-5])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[1]=int(shbuf[end-4])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[2]=int(shbuf[end-3])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[3]=int(shbuf[end-2])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[4]=int(shbuf[end-1])-sumvex(current_vex);
		face_index[current_vex][face_count].vp[5]=int(shbuf[end-0])-sumvex(current_vex);
		if(face_index[current_vex][face_count].vp[0]>max_p_count || face_index[current_vex][face_count].vp[1]>max_p_count || face_index[current_vex][face_count].vp[2]>max_p_count || face_index[current_vex][face_count].vp[3]>max_p_count || face_index[current_vex][face_count].vp[4]>max_p_count || face_index[current_vex][face_count].vp[5]>max_p_count){
			cout<<"Wrong vp parsing, larger than "<< max_p_count<<"\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		if(face_index[current_vex][face_count].vp[0]<0 || face_index[current_vex][face_count].vp[1]<0 || face_index[current_vex][face_count].vp[2]<0 || face_index[current_vex][face_count].vp[3]<0 || face_index[current_vex][face_count].vp[4]<0 || face_index[current_vex][face_count].vp[5]<0){
			cout<<"Wrong vp parsing, minus value\n";
			face_index[current_vex][face_count].vertex_count=0;
		}			
		cout<<"("<<face_index[current_vex][face_count].vp[0]<<","<<face_index[current_vex][face_count].vp[1]<<","<<face_index[current_vex][face_count].vp[2]<<","<<face_index[current_vex][face_count].vp[3]<<","<<face_index[current_vex][face_count].vp[4]<<","<<face_index[current_vex][face_count].vp[5]<<")  ";

	}
	else if(shbuf[end-12]==0x06){
		//6x2 points
		location=end-12;
		cout<<"(2,";hexprint(shbuf[end-12]);cout<<") ";
		face_index[current_vex][face_count].vertex_count=6;
		face_index[current_vex][face_count].vp[0]=int(shbuf[end-11])+int(shbuf[end-10])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[1]=int(shbuf[end-9])+int(shbuf[end-8])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[2]=int(shbuf[end-7])+int(shbuf[end-6])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[3]=int(shbuf[end-5])+int(shbuf[end-4])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[4]=int(shbuf[end-3])+int(shbuf[end-2])*256-sumvex(current_vex);
		face_index[current_vex][face_count].vp[5]=int(shbuf[end-1])+int(shbuf[end-0])*256-sumvex(current_vex);
		if(face_index[current_vex][face_count].vp[0]>max_p_count || face_index[current_vex][face_count].vp[1]>max_p_count || face_index[current_vex][face_count].vp[2]>max_p_count || face_index[current_vex][face_count].vp[3]>max_p_count || face_index[current_vex][face_count].vp[4]>max_p_count || face_index[current_vex][face_count].vp[5]>max_p_count){
			cout<<"Wrong vp parsing, larger than "<< max_p_count<<"\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		if(face_index[current_vex][face_count].vp[0]<0 || face_index[current_vex][face_count].vp[1]<0 || face_index[current_vex][face_count].vp[2]<0 || face_index[current_vex][face_count].vp[3]<0 || face_index[current_vex][face_count].vp[4]<0 || face_index[current_vex][face_count].vp[5]<0){
			cout<<"Wrong vp parsing, minus value\n";
			face_index[current_vex][face_count].vertex_count=0;
		}
		cout<<"("<<face_index[current_vex][face_count].vp[0]<<","<<face_index[current_vex][face_count].vp[1]<<","<<face_index[current_vex][face_count].vp[2]<<","<<face_index[current_vex][face_count].vp[3]<<","<<face_index[current_vex][face_count].vp[4]<<face_index[current_vex][face_count].vp[5]<<")  ";

	}



	if(location!=0){
		// found!
		return location;
	}else{
		return -1;
	}
}
	
//-----------------------------------




int ext(int ext_way){
    
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
// find all locations of ".PIC"

	for(int i=0;i<size;i++){
		if(shbuf[i]==0x2E && shbuf[i+1]==0x50 && shbuf[i+2]==0x49 && shbuf[i+3]==0x43){
			loc_pic[count_pic]=i;
			count_pic++;
		}
	}

    // if this shape is shadow, (***_S.sh), locate ".asm"
    /*
    if (count_pic == 0){
    	for(int i=0;i<size;i++){
		  if(shbuf[i]==0x2E && shbuf[i+1]==0x61 && shbuf[i+2]==0x73 && shbuf[i+3]==0x6D){
		      loc_pic[count_pic]=i;
		      count_pic++;
		  }
	   }
    }
    */

//--------------------------------------
// find all locations of "82 00"

	for(int i=loc_pic[0];i<size;i++){
		if( (shbuf[i]==0x00 || shbuf[i]==0x1E) && shbuf[i+1]==0x82 && shbuf[i+2]==0x00){
            if(preexam(i+1, shbuf[i+3]+shbuf[i+4]*256)){  // Do some pre-examined
            
					loc_cod[count_cod]=i+1;
					size_cod[count_cod]=shbuf[i+3]+shbuf[i+4]*256;
					start_cod[count_cod]=i+1+6;
					end_cod[count_cod]=i+1+6+(size_cod[count_cod]*6);
					
					cout<<count_cod<<":";
					for(int k=0;k<6;k++){
		            	if(shbuf[i+1+k] <= 0xF){
		             		printf("0%x ",shbuf[i+1+k]);
		                }else{
		                    printf("%x ",shbuf[i+1+k]); /* Large */
		                }
		            }
		            // print vertex headers
		            cout<<"\t("<<size_cod[count_cod]<<")";
		            cout<<"\t["<<start_cod[count_cod]<<" - "<<end_cod[count_cod]<<"]\n";
		            
		            
		            
					count_cod++;

        	}
		}
	}
//---------------------------------------
// create cod array
	for(int i=0;i<count_cod;i++){

			
            // for test, print hex after vertexs
            int next=0;
            int foundPN=0;
            int end_boundary=0;
            
            if(i == count_cod-1){// This section is to fine the last cods periods
                // try to find the end of face structures
                for(int findend=end_cod[i];findend<end_cod[i]+3000;findend++){
                    if(shbuf[findend] == 0x00 && shbuf[findend+1] == 0x00 && shbuf[findend+2] == 0x00 && shbuf[findend+3] == 0x00 && shbuf[findend+4] == 0x00 && shbuf[findend+5] == 0x00 && shbuf[findend+6] == 0x00 && shbuf[findend+7] == 0x00 && shbuf[findend+8] == 0x00 && shbuf[findend+9] == 0x00){
                        end_boundary=findend;
                        break;
                    }                
                }
                if(end_boundary==0){
                    end_boundary=end_cod[i]+2000;
                }

            }else{
                end_boundary=start_cod[i+1]-6;
            }
            
            cout<<"["<<i<<"]-----------------------------------\n";    
			face_count[i]=0; 
			for(int z=end_cod[i];z<end_boundary;z++){ // the last cods has no the next start_cod[i+1]-6
                if (shbuf[z]==0xfc){ // 0xFC should be handled first
				   if(shbuf[z+1]==0x41){
                   		cout<<"\n[FC 41]: ";//65
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }else if(shbuf[z+1]==0x61){
                   		cout<<"\n[FC 61]: ";//97
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }else if(shbuf[z+1]==0x63){
                   		cout<<"\n[FC 63]: ";//99
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }else if(shbuf[z+1]==0x44){
                   		cout<<"\n[FC 44]: ";//68
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }else if(shbuf[z+1]==0x64){
                   		cout<<"\n[FC 64]: ";//100
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }else if(shbuf[z+1]==0xEE){
                   		cout<<"\n[FC EE]: ";//238
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }else if(shbuf[z+1]==0xED){
                   		cout<<"\n[FC ED]: ";//237
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }else if(shbuf[z+1]==0x6C){
                   		cout<<"\n[FC 6C]: ";//108
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }else if(shbuf[z+1]==0x4C){
                   		cout<<"\n[FC 4C]: ";//76
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }else if(shbuf[z+1]==0xFE){
                   		cout<<"\n[FC FE]: ";//254
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }else if(shbuf[z+1]==0x73){
                   		cout<<"\n[FC 73]: ";//115
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }else if(shbuf[z+1]==0xFD){
                   		cout<<"\n[FC FD]: ";//253
                   		next=lookingFC(z);
                   		if(next==-1){next=23;}
                   		foundPN=findPN(z,z+next-1,i,(int)shbuf[z+1],face_count[i],size_cod[i],ext_way);
                   		for(int y=0;y<next;y++){
                           hexprint(shbuf[z+y]);                   
                   		}
                  		cout<<"\n";
                  		z=z+next-1;
                  		face_count[i]++;
                   		continue; 						
				   }				   
				                   
                }else if(shbuf[z]==0xf6){
                   cout<<"[F6]: ";
                   for(int y=0;y<7;y++){
                           hexprint(shbuf[z+y]);
                   }
                   
                   cout<<"\t Normals = ";
                   for(int zz=0;zz<3;zz++){
                           if((int)shbuf[z+4+zz]>=128){
                              cout<<(int)shbuf[z+4+zz]-256;
                           }else{
                              cout<<(int)shbuf[z+4+zz];
                           }
                           cout<<",";
                   }
                   cout<<"\n";
                   z=z+6;
                   continue;
                }else if(shbuf[z]==0x06){ //print 06 item
                   cout<<"[06]: ";
                   for(int y=0;y<21;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+20;
                   continue;                
                }else if(shbuf[z]==0x0c){ //print 0c item
                   cout<<"[0C]: ";
                   for(int y=0;y<17;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+16;
                   continue;                
                }else if(shbuf[z]==0x0E){ //print 0E item
                   cout<<"[0E]: ";
                   for(int y=0;y<17;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+16;
                   continue;                
                }else if(shbuf[z]==0x10){ //print 10 item
                   cout<<"[10]: ";
                   for(int y=0;y<17;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+16;
                   continue;                
                }else if(shbuf[z]==0x12){ //print 12 item
                   cout<<"[12]: ";
                   for(int y=0;y<7;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+6;
                   continue;                
                }else if(shbuf[z]==0x2E){ //print 2E item
                   cout<<"[2E]: ";
                   for(int y=0;y<8;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+7;
                   continue;                
                }else if(shbuf[z]==0x40){ //print 40 item
                   cout<<"[40]: ";
                   for(int y=0;y<12;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+11;
                   continue;                
                }else if(shbuf[z]==0x48){ //print 48 item
                   cout<<"[48]: ";
                   for(int y=0;y<4;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+3;
                   continue;                
                }else if(shbuf[z]==0x4D){ //print 4D item
                   cout<<"[4D]: ";
                   for(int y=0;y<4;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+3;
                   continue;                
                }else if(shbuf[z]==0x50){ //print 50 item
                   cout<<"[50]: ";
                   for(int y=0;y<8;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+7;
                   continue;                
                }else if(shbuf[z]==0x6C){ //print 6C item
                   cout<<"[6C]: ";
                   for(int y=0;y<13;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+12;
                   continue;                
                }else if(shbuf[z]==0xBC){ //print BC item
                   cout<<"[BC]: ";
                   for(int y=0;y<8;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+7;
                   continue;                
                }else if(shbuf[z]==0xD0){ //print D0 item
                   cout<<"[D0]: ";
                   for(int y=0;y<4;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+3;
                   continue;                
                }else if(shbuf[z]==0xE0){ //print E0 item
                   cout<<"[E0]: ";
                   for(int y=0;y<4;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+3;
                   continue;
				                   
                }else if(shbuf[z]==0x1e){
                   cout<<"[1E]: ";
                   for(int y=0;y<1;y++){
                           hexprint(shbuf[z+y]);                   
                   }
                   cout<<"\n";
                   z=z+0;
                   continue;
                }                
                hexprint(shbuf[z]);
               

//0xFC
//0x41, 0x61, 0x63: No U,Vs present.
//0x44, 0x64: 8 bit UVs present
//0xEE, 0xED, 0x6C, 0x4C: 8 or 16 bit UVs

//FC FE
//FC 54
//FC 5C

//Struct 0x06 size 21..OK
//Struct 0x0C size 17..OK
//Struct 0x0E size 17..OK
//Struct 0x10 size 17..Ok
//Struct 0x12 size 7..OK
//Struct 0x1E size one (Used for padding and I guess for data alignment)
//Struct 0x2E size 8..OK
//Struct 0x40 size 12...OK
//Struct 0x48 size 4 bytes ...OK
//Struct 0x4D size 4 bytes...OK
//Struct 0x50 size 8...OK
//Struct 0x6C size 13...OK
//Struct 0xBC size 8...OK
//Struct 0xD0 size 4 bytes...OK
//Struct 0xE0 size 4 bytes...OK
//Struct 0xF0 variable length block delimited by 0x1E
//Struct 0xFF size 12 or 14


            }
            // last part does not be printed.
            cout<<"\n";
            // for test, print 20 hex after vertexs  
            
          
		cod_index[i]=new cod_st[size_cod[i]];
		// copy hex data to array.
		for(int j=0;j<size_cod[i];j++){
			cod_index[i][j].mash_id=i;
			cod_index[i][j].cod_id=j;
			for(int k=0;k<6;k++){
				cod_index[i][j].cod_hex[k]=shbuf[(loc_cod[i]+6)+j*6+k];
				//cout<<"test:"<<k<<":"<<cod_index[i][j].cod_hex[k]<<"\n";
			}
			cod_index[i][j].x=hex2xyz(cod_index[i][j].cod_hex[0],cod_index[i][j].cod_hex[1]);
			cod_index[i][j].y=hex2xyz(cod_index[i][j].cod_hex[2],cod_index[i][j].cod_hex[3]);
			cod_index[i][j].z=hex2xyz(cod_index[i][j].cod_hex[4],cod_index[i][j].cod_hex[5]);
   				// print point data for ref
   				
				cout<<"Point["<<i<<"]["<<j<<"]:[";
				hexprint(cod_index[i][j].cod_hex[0]);
				hexprint(cod_index[i][j].cod_hex[1]);
				hexprint(cod_index[i][j].cod_hex[2]);
				hexprint(cod_index[i][j].cod_hex[3]);
				hexprint(cod_index[i][j].cod_hex[4]);
				hexprint(cod_index[i][j].cod_hex[5]);
				cout<<"]("<<cod_index[i][j].x<<","<<cod_index[i][j].y<<","<<cod_index[i][j].z<<")\n";
				
   				// print point data for ref

		}
	}
	
//---------------------------------------
// create output file
// example: VEX_DSTTRP.SH_0_20_601.TXT
//
    char tmpFileName[50];
    char tmp[20]="tmp_";
    strcat (tmp, shFileName);
    mkdir(tmp);
    //strcpy (tmp, shFileName);
    //mkdir(shFileName);
	for(int i=0;i<count_cod;i++){
            tmpFileName[0]='\0';
            tmp[0]='\0';
            strcpy (tmpFileName, "tmp_");
            strcat (tmpFileName, shFileName);
            strcat(tmpFileName, "\\");
            strcat(tmpFileName, "VEX_");
            strcat (tmpFileName, shFileName);
            strcat (tmpFileName, "_");
            itoa(count_cod, tmp, 10);
            strcat (tmpFileName, tmp);  
            strcat (tmpFileName, "_");
            itoa(i, tmp, 10);
            strcat (tmpFileName, tmp);
            strcat (tmpFileName, "_");
            itoa(size_cod[i], tmp, 10);
            strcat (tmpFileName, tmp);
            strcat (tmpFileName, "_");
            itoa(start_cod[i], tmp, 10);
            strcat (tmpFileName, tmp);
            strcat (tmpFileName, "_.TXT");
            //cout<<tmpFileName<<"\n";
            if((vexFile[i]=fopen(tmpFileName,"wt"))==NULL){
                cout<<"tmp vertex files create error!\n";
                exit(0);
            }else{
                fclose(vexFile[i]);
                // output the vertex data to each file
                ofstream fout(tmpFileName);
                for(int j=0;j<size_cod[i];j++){                        
	            		fout<<cod_index[i][j].x<<","<<cod_index[i][j].y<<","<<cod_index[i][j].z<<"\n";
//                        fout<<cod_index[i][j].x<<";"<<cod_index[i][j].y<<";"<<cod_index[i][j].z<<";"<<j<<"\n";
                }
                
            }            

            // output edge file
            tmpFileName[0]='\0';
            tmp[0]='\0';
            strcpy (tmpFileName, "tmp_");
            strcat (tmpFileName, shFileName);
            strcat(tmpFileName, "\\");
            strcat(tmpFileName, "EDG_");
            strcat (tmpFileName, shFileName);
            strcat (tmpFileName, "_");
            itoa(count_cod, tmp, 10);
            strcat (tmpFileName, tmp);  
            strcat (tmpFileName, "_");
            itoa(i, tmp, 10);
            strcat (tmpFileName, tmp);
            strcat (tmpFileName, "_");
            itoa(size_cod[i], tmp, 10);
            strcat (tmpFileName, tmp);
            strcat (tmpFileName, "_");
            itoa(start_cod[i], tmp, 10);
            strcat (tmpFileName, tmp);
            strcat (tmpFileName, "_.TXT");
            if((edgFile[i]=fopen(tmpFileName,"wt"))==NULL){
                cout<<"tmp edges files create error!\n";
                exit(0);
            }else{
                fclose(edgFile[i]);
                // output the vertex data to each file
                ofstream fout(tmpFileName);
                for(int j=0;j<500;j++){
					if(face_index[i][j].vertex_count==0){
						cout<<"====:"<<i<<","<<j<<":"<<face_index[i][j].face_id<<","<<face_index[i][j].vertex_count<<"\n";
					}else{                         
						cout<<"====:"<<i<<","<<j<<":"<<face_index[i][j].face_id<<","<<face_index[i][j].vertex_count<<"\n";
						for(int q=0;q<face_index[i][j].vertex_count-1;q++){
							fout<<face_index[i][j].vp[q]<<","<<face_index[i][j].vp[q+1]<<"\n";
						}
							fout<<face_index[i][j].vp[face_index[i][j].vertex_count-1]<<","<<face_index[i][j].vp[0]<<"\n";
						
					}
//	            		fout<<cod_index[i][j].x<<","<<cod_index[i][j].y<<","<<cod_index[i][j].z<<"\n";
//                        fout<<cod_index[i][j].x<<";"<<cod_index[i][j].y<<";"<<cod_index[i][j].z<<";"<<j<<"\n";
                }
                
            }
///*
            // output face file
            tmpFileName[0]='\0';
            tmp[0]='\0';
            strcpy (tmpFileName, "tmp_");
            strcat (tmpFileName, shFileName);
            strcat(tmpFileName, "\\");
            strcat(tmpFileName, "FAC_");
            strcat (tmpFileName, shFileName);
            strcat (tmpFileName, "_");
            itoa(count_cod, tmp, 10);
            strcat (tmpFileName, tmp);  
            strcat (tmpFileName, "_");
            itoa(i, tmp, 10);
            strcat (tmpFileName, tmp);
            strcat (tmpFileName, "_");
            itoa(size_cod[i], tmp, 10);
            strcat (tmpFileName, tmp);
            strcat (tmpFileName, "_");
            itoa(start_cod[i], tmp, 10);
            strcat (tmpFileName, tmp);
            strcat (tmpFileName, "_.TXT");
            if((edgFile[i]=fopen(tmpFileName,"wt"))==NULL){
                cout<<"tmp edges files create error!\n";
                exit(0);
            }else{
                fclose(edgFile[i]);
                // output the vertex data to each file
                ofstream fout(tmpFileName);
                for(int j=0;j<500;j++){
					if(face_index[i][j].vertex_count==0){
					}else{                         
						for(int q=0;q<face_index[i][j].vertex_count-1;q++){
							fout<<face_index[i][j].vp[q]<<",";
						}
						fout<<face_index[i][j].vp[face_index[i][j].vertex_count-1]<<"\n";
					}
//	            		fout<<cod_index[i][j].x<<","<<cod_index[i][j].y<<","<<cod_index[i][j].z<<"\n";
//                        fout<<cod_index[i][j].x<<";"<<cod_index[i][j].y<<";"<<cod_index[i][j].z<<";"<<j<<"\n";
                }
                
            }              
            
//*/            
    }
   




//---------------------------------------

	 // code information print all
	 /*
	for(int i=0;i<count_cod;i++){
		for(int j=0;j<size_cod[i];j++){
			cout<<"mesh_id["<<cod_index[i][j].mash_id<<"]";
			cout<<"cod_id["<<cod_index[i][j].cod_id<<"]("<<cod_index[i][j].x<<","<<cod_index[i][j].y<<","<<cod_index[i][j].z<<")\n";

		}
	}
	*/
	// mesh 0 code information print
	/*
    for(int j=0;j<size_cod[0];j++){
			cout<<cod_index[0][j].x<<","<<cod_index[0][j].y<<","<<cod_index[0][j].z<<"\n";
	}
    */
	
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
	
	// load vertex files

	work_dir[0]='\0';
    strcpy (work_dir, "tmp_");
    strcat (work_dir, shFileName);
	if( (_access( work_dir, 0 )) != -1 ) {
		//cout<<"Work tmp dir of vertex files exists\n";

	}else{
		cout<<"Work tmp dir of vertex files does not exist\n";
		exit(0);
	}
	
	// count how many vertex files in dir
    DIR * dp = opendir(work_dir);
    int file_count=0;
    char files[50][100];
    struct file_item{
		char shfilename[50];
		int totalvex;
		int currentvex;
		int vex_cnt;
		int vex_start;	
	}
    file_item[50];
	char *delim = "_";
	char * pch;
	FILE *vexFile;
	char realfilelocation[200];
	char tmp[50];
	int line_cnt=0;
    
    struct dirent *filename; 
	while((filename=readdir(dp))){
         if(!strcmp(filename->d_name,"..") || !strcmp(filename->d_name,".")){  
			continue;  
		}

		// get information in filename
		strcpy (files[file_count], filename->d_name);

		pch = strtok(files[file_count],delim);// output:VEX

		if(pch[0]=='E' || pch[1]=='D' || pch[2]=='G'){
			// That is not VEX files, don't process it.
			continue; 
		}	
		if(pch[0]=='F' || pch[1]=='A' || pch[2]=='C'){
			// That is not VEX files, don't process it.
			continue; 
		}
					
		pch = strtok (NULL, delim);// output:sh file name
		// Noting! if it is shadow file, minor error, SU35B_S.SH ->SU35BS.SH
        // do compare, if error, use shFileName instead.
        if(strcmp(shFileName,pch)){
            // pch is different with real shfile name, should be shadow file
            strcpy(file_item[file_count].shfilename, shFileName);
            pch = strtok (NULL, delim);// do a more
        }else{
    		strcpy(file_item[file_count].shfilename, pch);
        }
        //cout<<"shfilename = "<<file_item[file_count].shfilename<<"\n";
                
		pch = strtok (NULL, delim);// output: totalvex
		file_item[file_count].totalvex=atoi(pch);
		//cout<<"totalvex = "<<file_item[file_count].totalvex<<"\n";
		
		pch = strtok (NULL, delim);// output: currentvex
		file_item[file_count].currentvex=atoi(pch);
		//cout<<"currentvex = "<<file_item[file_count].currentvex<<"\n";		
		
		pch = strtok (NULL, delim);// output: vex_cnt
		file_item[file_count].vex_cnt=atoi(pch);
		//cout<<"vex_cnt = "<<file_item[file_count].vex_cnt<<"\n";	
		
		pch = strtok (NULL, delim);// output: vex_start
		file_item[file_count].vex_start=atoi(pch);
		//cout<<"vex_start = "<<file_item[file_count].vex_start<<"\n";	

		// read file and tran Vertex to HEX
		strcpy(realfilelocation,work_dir);
		strcat(realfilelocation,"\\");
		strcat(realfilelocation,filename->d_name);
	    
	    
//		if((vexFile=fopen(realfilelocation,"rt"))==NULL){
//			cout<<"open "<<realfilelocation<<" error!\n";
//			exit(0);
//		}
		ifstream in(realfilelocation);
  		if(!in){
			cout<<"open "<<realfilelocation<<" error!\n";
			exit(0);			
		}
		line_cnt=0;
 		while(in){  
			in.getline(tmp,50);
			xyz2hex(tmp,file_item[file_count].vex_start+(line_cnt*6));
			line_cnt++;
  		}
		file_count++;
	}
	// put back modified shbuf to file.
	// load original sh file
	if((shFile=fopen(shFileName,"wb"))==NULL){
		cout<<"sh File, ("<<shFileName<<") open for wrinting error !\n";
		exit(0);

	}	
    fwrite(shbuf,1,size,shFile); // write Class File
	fclose(shFile);				// Close Class File


}

//-----------------------------------

int main(int arguments_count,char *arguments[]){
    if(arguments_count!=3){
		cout<<"Usage: fash <options> <*.sh>..."<<"\n\n";
		exit(0);	
    }
    else{
		op=arguments[1];
		shFileName = arguments[2];		
	}
    //ofstream log("Log.txt");
    //log<<" The shape : "<<shFileName<<" is parsed as follows.\n";
    //log<<"---------------------------------------------------\n";
	if(op[0]=='e'){
	// eXtract vertex files from sh file (newer way)
		ext(0);
	
	}else if (op[0]=='o'){
	// eXtract vertex files from sh file (older way)
		ext(1);
	}else if (op[0]=='b'){
	// Build vertex files to sh file
		build();
	}else{
		cout<<"Wrong op.\n";
		exit(0);
	}

 return 0;   
}
	
	
