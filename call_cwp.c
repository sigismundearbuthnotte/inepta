#include "cwp.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <time.h>

void read_table(int rows,int cols,const char *fileName,float *table,bool skip1st)
{
	const int max_line_length=10000;//that really should be sufficient
	char *buff;
	buff=(char*)malloc(sizeof(char)*max_line_length);
	char **b2;
	b2=&buff;
	FILE *fp;
	fp=fopen(fileName,"r");
	size_t n;
    char num[100];//a single value
    int count=-1;
	for (int r=0;r<rows;++r)
	{
        getline(b2,&n,fp);
        int rPos=0;
        for (int c=0;c<cols;++c)
        {
            while (buff[rPos]==' '||buff[rPos]=='\t'||buff[rPos]==',')
                ++rPos;
            int cPos=0;
            while ((buff[rPos]>='0'&&buff[rPos]<='9')||buff[rPos]=='.')
            {
                num[cPos]=buff[rPos];
                ++rPos;
                ++cPos;
            }
            num[cPos]=0;
            if (c>0||!skip1st)
                table[++count]=atof(num);
        }
    }
    free(buff);
    fclose(fp);
}

const int numPols=100000, numOutputs=4;

int main(int argc, char *argv[])
{
struct futhark_context_config * cfg = futhark_context_config_new();
struct futhark_context * ctx = futhark_context_new(cfg);

//read tables, simply!
float *lapse, *matypropnas, *mort, *renexps, *revbonus, *surrpropnas;
matypropnas = (float*)  malloc(1*sizeof(float));
mort = (float*)  malloc(100*sizeof(float));
renexps = (float*)  malloc(1*sizeof(float));
revbonus = (float*)  malloc(1*sizeof(float));
lapse = (float*)  malloc(1*sizeof(float));
surrpropnas = (float*)  malloc(1*sizeof(float));
read_table(1,2,"/home/andrew/inepta/tables/lapse",lapse,true);
read_table(1,2,"/home/andrew/inepta/tables/revbonus",revbonus,true);
read_table(1,2,"/home/andrew/inepta/tables/renexps",renexps,true);
read_table(1,2,"/home/andrew/inepta/tables/matypropnas",matypropnas,true);
read_table(1,2,"/home/andrew/inepta/tables/surrpropnas",surrpropnas,true);
read_table(100,2,"/home/andrew/inepta/tables/mort",mort,true);

//create Futhark arrays for tables
struct futhark_f32_2d *fut_mort=futhark_new_f32_2d(ctx, mort,100,1);
struct futhark_f32_2d *fut_lapse=futhark_new_f32_2d(ctx, lapse,1,1);
struct futhark_f32_2d *fut_matypropnas=futhark_new_f32_2d(ctx, matypropnas,1,1);
struct futhark_f32_2d *fut_renexps=futhark_new_f32_2d(ctx, renexps,1,1);
struct futhark_f32_2d *fut_revbonus=futhark_new_f32_2d(ctx, revbonus,1,1);
struct futhark_f32_2d *fut_surrpropnas=futhark_new_f32_2d(ctx, surrpropnas,1,1);

//read data
int *dataInt;
float *dataFloat, *dataAll;
dataInt = (int*)  malloc(numPols*8*sizeof(int));
dataAll = (float*)  malloc(numPols*12*sizeof(float));
dataFloat = (float*)  malloc(numPols*4*sizeof(float));
read_table(numPols,12,"/home/andrew/inepta/data/cwp1.data",dataAll,false);
for (int p=0;p<numPols;++p)
{
    int startInt,startAll,startFloat;
    startAll=p*12;
    startInt=p*8;
    startFloat=p*4;

    for (int i=0;i<8;++i)
        dataInt[startInt+i]=(int)dataAll[startAll+i];

    for (int i=0;i<4;++i)
        dataFloat[startFloat+i]=dataAll[startAll+8+i];
}

//create Futhark arrays for data
struct futhark_i32_2d *fut_dataInt=futhark_new_i32_2d(ctx,dataInt,numPols,8);
struct futhark_f32_2d *fut_dataFloat=futhark_new_f32_2d(ctx,dataFloat,numPols,4);

//Futhark results (in this case it's 2-d, with a number of items (OK,1) per policy)
struct futhark_f32_2d *futRes;
float *futResC=(float*) malloc(numOutputs*numPols*sizeof(float));

int32_t numPeriods=600;

//call Futhark
struct timespec startTime,endTime;
clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&startTime);
int futErr=futhark_entry_main(ctx,&futRes,fut_dataInt,fut_dataFloat,numPeriods,fut_mort,fut_lapse,fut_revbonus,fut_renexps,fut_surrpropnas,fut_matypropnas);
clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&endTime);
double diffTime=(endTime.tv_sec-startTime.tv_sec)+(endTime.tv_nsec-startTime.tv_nsec)/1e9;

//get results
futhark_values_f32_2d(ctx,futRes,futResC);

//Print results for last policy
for (int i=0;i<numOutputs;++i)
    printf("%f\n",futResC[numOutputs*(numPols-1)+i]);
printf("%f\n",diffTime);

//free data, tables, results arrays
free(lapse);
free(matypropnas);
free(mort);
free(renexps);
free(revbonus);
free(surrpropnas);
free(dataInt);
free(dataFloat);
free(futResC);

//free Futhark arrays
futhark_free_f32_2d(ctx,fut_lapse);
futhark_free_f32_2d(ctx,fut_matypropnas);
futhark_free_f32_2d(ctx,fut_mort);
futhark_free_f32_2d(ctx,fut_renexps);
futhark_free_f32_2d(ctx,fut_revbonus);
futhark_free_f32_2d(ctx,fut_surrpropnas);
futhark_free_i32_2d(ctx,fut_dataInt);
futhark_free_f32_2d(ctx,fut_dataFloat);
futhark_free_f32_2d(ctx,futRes);

//free Futhark context
futhark_context_free(ctx);
futhark_context_config_free(cfg);

return 0;
}
