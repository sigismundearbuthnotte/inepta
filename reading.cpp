//reading data, table and esg
//use c++ so can use streams!
#include <string>

using namespace std;

extern "C" int readTable(const char* fileName,const char* baseSubdir, int numDims,int basisType,int**dimSizes,float **table);
extern "C" int readData(const char*fileName,const char* subdir,int numFields,int *intOrReal, int*arraySize,int *numPols,float **tableReal,int **tableInt);
extern "C" int readESG(const char*fileName,const char* subdir,int numFields,int*arraySize1,int*arraySize2,int*numPeriods,int*numScens,float**scens);

const int basisSingle=1;
const int basisPrefix=2;
const int basisSuffix=3;
const int basisSubdir=4;

int readTable(const char* fileName,const char* baseSubdir, int numDims,int basisType,int**dimSizes,float **table)
{
}

int readData(const char*fileName,const char* subdir,int numFields,int *intOrReal, int*arraySize,int *numPols,float **tableReal,int **tableInt)
{
}

int readESG(const char*fileName,const char* subdir,int numFields,int*arraySize1,int*arraySize2,int*numPeriods,int*numScens,float**scens)
{
}