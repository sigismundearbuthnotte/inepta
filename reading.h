int readTable(const char* fileName,const char* baseSubdir, int numDims,int*dimSizes,int numBases,const char* bases[],int basisType,float **table,int*lb,const char *bo[]);
int readData(const char*fileName,const char* subdir,int numFields,int *intOrReal,const char **enumInfo[], int numEnums, int*arraySize,int *numPols,float **dataReal,int **dataInt);
int readESG(const char*fileName,const char* subdir,int numScens,int numFields,int*numPeriods,float**scens);
void freeReals(float *p);
void freeInts(int *p);
