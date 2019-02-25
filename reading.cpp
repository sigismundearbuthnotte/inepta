//reading data, table and esg
//use c++ so can use streams!
#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <stdlib.h>
#include <cstdlib>

using namespace std;

extern "C" int readTable(const char* fileName,const char* baseSubdir, int numDims,int*dimSizes,int numBases,const char* bases[],int basisType,float **table,int*lb);
extern "C" int readData(const char*fileName,const char* subdir,int numFields,int *intOrReal, int*arraySize,int *numPols,float **dataReal,int **dataInt);
extern "C" int readESG(const char*fileName,const char* subdir,int numScens,int numFields,int*numPeriods,float**scens);
extern "C" void freeReals(float *p);
extern "C" void freeInts(int *p);

const int basisSingle=1;
const int basisPrefix=2;
const int basisSuffix=3;
const int basisSubdir=4;

int readTable(const char* fileName,const char* baseSubdir, int numDims,int*dimSizes,int numBases,const char* bases[],int basisType,float **table,int*lb)
{
    string fName,line,lTemp;
    ifstream inFile;
    istringstream l;
    int numLines,lineLength;

    //assume all files are the same size and get the block size of the first
    //recall: the outer dimensions are enums (so their size is known) and the inner two (or one) are integers whose size is not known
    //a dimSize of -1 indicates an int
    if (basisType==basisSingle)
        fName=string(baseSubdir)+"/"+string(fileName);
    if (basisType==basisPrefix)
        fName=string(baseSubdir)+"/"+string(bases[0])+"_"+string(fileName);
    if (basisType==basisSuffix)
        fName=string(baseSubdir)+"/"+string(fileName)+"_"+bases[0];
    if (basisType==basisSubdir)
        fName=string(baseSubdir)+"/"+string(bases[0])+"/"+string(fileName);
    inFile.open(fName.c_str());
    if (!inFile.is_open())
        return -1;

    //get number of inner dimensions (the block dimension == 1 or 2)
    //if therer's only
    int numIntDims=1;
    if (dimSizes[numDims-2]==-1)
        numIntDims=2;

    //number of blocks based on outer dimensions
    int numBlocks=1;
    for (int i=0;i<=numDims-3;++i)
        numBlocks*=dimSizes[i];

    //read first block
    getline(inFile,line);
    while (line[0]!='~')//find block header
        getline(inFile,line);
    getline(inFile,line);//indexing header
    l.clear();
    l.str(line);//get first column index for lower bound purposes
    l>>lTemp;
    char*p;
    long convI=std::strtol(lTemp.c_str(),&p,10);
    if (*p)//if successful, p points to NULL end of string, so a "true" values indicates failure
        lb[1]=0;
    else
        lb[1]=(int) convI;
    getline(inFile,line);//first line

    l.clear();
    l.str(line);//get line length
    for (lineLength=0;!l.eof();++lineLength)
    {
        l>>lTemp;
        if (lineLength==0)//get first row index for lower bounds
        {
            long convI=std::strtol(lTemp.c_str(),&p,10);
            if (*p)//if successful, p points to NULL end of string, so a "true" value indicates failure
                lb[0]=0;
            else
                lb[0]=(int) convI;
        }
    }
    lineLength--;//ignore index at start of line

    numLines=1;//count remainder of lines
    while (!inFile.eof()&&line[0]!='~')
    {
        getline(inFile,line);
        if (line[0]!='*')
            numLines++;
    }
    if (line[0]=='~')
        numLines--;

    //return integer dim sizes
    if (numIntDims==2)
    {
        dimSizes[numDims-2]=numLines;
        dimSizes[numDims-1]=lineLength;
    }
    else
        dimSizes[numDims-1]=numLines;

    inFile.close();

    //create array to hold all files as one big table (1-d as it'll be reshaped by futhark)
    (*table)=new float[numBases*numBlocks*numLines*lineLength];

    //loop through files
    int tablePos=0;
    for (int basis=0;basis<numBases;++basis)
    {

        if (basisType==basisSingle)
            fName=string(baseSubdir)+"/"+string(fileName);//yes, we are going to repeat the same file over and over; so shoot me
        if (basisType==basisPrefix)
            fName=string(baseSubdir)+"/"+string(bases[basis])+"_"+string(fileName);
        if (basisType==basisSuffix)
            fName=string(baseSubdir)+"/"+string(fileName)+"_"+bases[basis];
        if (basisType==basisSubdir)
            fName=string(baseSubdir)+"/"+string(bases[basis])+"/"+string(fileName);
        inFile.open(fName.c_str());
        if (!inFile.is_open())
            return -1;

        for (int block=0;block<numBlocks;++block)
        {
            getline(inFile,line);
            while (line[0]=='~'||line[0]=='*')
                getline(inFile,line);
            getline(inFile,line);
            for (int ll=0;ll<numLines;++ll)
            {
                l.clear();
                l.str(line);
                l>>lTemp;
                for (int col=0;col<lineLength;++col)
                    l>>(*table)[tablePos++];
                getline(inFile,line);
            }
        }

        inFile.close();
    }

    return 0;
}

int readData(const char*fileName,const char* subdir,int numFields,int *intOrReal, int*arraySize,int *numPols,float **dataReal,int **dataInt)
{
    string fName,line,lTemp;
    ifstream inFile;
    istringstream l;

    fName=string(subdir)+"/"+string(fileName);
    inFile.open(fName.c_str());
    if (!inFile.is_open())
        return -1;

    int numReal=0,numInt=0,numTot=0;
    for (int i=0;i<numFields;++i)
        numTot+=arraySize[i];
    bool *intOrReal2;//the parameter does not allow for array length
    intOrReal2=new bool[numTot];
    int k=0;
    for (int i=0;i<numFields;++i)
        if (intOrReal[i]==0)
        {
            numInt+=arraySize[i];
            for (int j=0;j<arraySize[i];++j)
                intOrReal2[k++]=true;
        }
        else
        {
            numReal+=arraySize[i];
            for (int j=0;j<arraySize[i];++j)
                intOrReal2[k++]=false;
        }

    getline(inFile,line);
    (*numPols)=atoi(line.c_str());
    (*dataReal)=new float[(*numPols)*numReal];
    (*dataInt)=new int[(*numPols)*numInt];
    int dataPosInt=0,dataPosReal=0;

    for (int pol=0;pol<(*numPols);++pol)
    {
        getline(inFile,line);
        l.clear();
        l.str(line);
        k=-1;
        for (int fld=0;fld<numTot;++fld)
        {
            ++k;
            if (intOrReal2[k])
                l>>(*dataInt)[dataPosInt++];
            else
                l>>(*dataReal)[dataPosReal++];
        }
    }
    return 0;
}

int readESG(const char*fileName,const char* subdir,int numScens,int numFields,int*numPeriods,float**scens)
//numFields is total number (i.e. adding in array/vector total length)
{
    string fName,line,lTemp;
    ifstream inFile;
    istringstream l;

    fName=string(subdir)+"/"+string(fileName);
    inFile.open(fName.c_str());
    if (!inFile.is_open())
        return -1;

    getline(inFile,line);
    while (line[0]!='~')//find block header
        getline(inFile,line);

    //determine number of periods
    getline(inFile,line);
    for (*numPeriods=1;!l.eof()&&line[0]!='~';++(*numPeriods))
        getline(inFile,line);
    --(*numPeriods);
    inFile.close();

    (*scens)=new float[numScens*(*numPeriods)*numFields];
    int schPos=0;
    inFile.open(fName.c_str());
    for (int scen=1;scen<=numScens;++scen)
    {
        getline(inFile,line);
        while (line[0]!='~')//find block header
            getline(inFile,line);
        for (int t=0;t<(*numPeriods);++t)
        {
            getline(inFile,line);
            l.clear();
            l.str(line);
            int tt;
            l>>tt;
            for (int fld=0;fld<numFields;++fld)//incude time
                l>>(*scens)[schPos++];
        }
    }
    inFile.close();
    return 0;
}

void freeReals(float *p)
{
    delete[]p;
}

void freeInts(int *p)
{
    delete[]p;
}
