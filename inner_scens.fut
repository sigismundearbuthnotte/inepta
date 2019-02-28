--MT based on mt19937ar.c by Nishimura and Matsumoto (2002)
let numRNsPerPeriod:u32=20--for the sake of argument
let numPeriods:u32=300
let numItems=20
let numRNsPerScen=numRNsPerPeriod*numPeriods
let numScens:u32=10000
let numScensPerBatch:u32=1000--ftsoa
let numRNsPerBatch=numRNsPerScen*numScensPerBatch
let numMTItersPerBatch:u32=10--ftsoa; i.e. how many ierations do we run the MT
let numBlocksOf624PerBatch:u32=1+numRNsPerBatch//(624*numMTItersPerBatch)--let's assume it doesn't divide exactly
let seeds:[]u32=5984...(5984+numBlocksOf624PerBatch-1)
let maxInt:u32=2**32-1
let maxIntF:f64=f64.u32 maxInt

let N:i32=624
let M:i32=397
let MATRIX_A:u32=0X9908b0df
let UPPER_MASK:u32=0X80000000
let LOWER_MASK:u32=0X7fffffff

let init(s:u32):[N]u32=
    let ret:*[N]u32=[s]++(replicate (N-1) 0u32)
in loop ret':*[N]u32=ret for i<(N-1) do ret' with [i+1]=1812433253u32*(ret'[i]^(ret'[i]>>30))+(u32.i32 i)+1u32

let initBlocksOf624:[][]u32=map init seeds

let nextBlockOf624 (b:[]u32):([]u32,[]f64)=
    let y =map2 (|) (map (&UPPER_MASK) b[0:N-M]) (map (&LOWER_MASK) b[1:N-M+1])
    let b1=map2 (^) (map2 (^) b[M:] (map (>>1) y)) (map (\x->if x&1u32==0 then 0 else MATRIX_A) y)
    let y' =map2 (|) (map (&UPPER_MASK) b[N-M:N-1]) (map (&LOWER_MASK) b[N-M+1:N])
    let b2=map2 (^) (map2 (^) b1[:M-1] (map (>>1) y')) (map (\x->if x&1u32==0 then 0 else MATRIX_A) y')
    let y''=(b[N-1]&UPPER_MASK)|(b1[0]&LOWER_MASK)
    let b3=b2[2*M-1-N]^(y''>>1)^(if y''&1u32==0 then 0 else MATRIX_A)

    let temperTemper(y:u32):u32=
        let y1=y^(y>>11)
        let y2=y1^((y1<<7)&0X9d2c5680)
        let y3=y2^((y2<<15)&0Xefc60000)
        in y3^(y3>>18)

    let b4=b1++b2++[b3]
in (b4,map (temperTemper >-> f64.u32 >-> (/maxIntF)) b4)

--see Glasserman p68
let BSMNormInv(x:f64)=
    let a0:f64=2.50662823884
    let a1:f64=(-18.61500062529)
    let a2:f64=41.391119773534
    let a3:f64=25.44106049637
    let b0:f64=8.47351093090
    let b1:f64=23.08336743743
    let b2:f64=(-21.06224101826)
    let b3:f64=3.13082909833
    let c0:f64=0.3374754822726147
    let c1:f64=0.9761690190917186
    let c2:f64=0.1607979714918209
    let c3:f64=0.0276438810333863
    let c4:f64=0.0038405729373609
    let c5:f64=0.0003951896511919
    let c6:f64=0.0000321767881768
    let c7:f64=0.0000002888167364
    let c8:f64=0.0000003960315187
    let y=x-0.5f64
    let ret= 
    if (y<0.42f64) && (y>(-0.42f64)) then
        let r=y*y
        in y*(((a3*r+a2)*r+a1)*r+a0)/((((b3*r+b2)*r+b1)*r+b0)*r+1)
    else
        let r'=if y>0 then x else 1-x
        let r=f64.log(-f64.log r')
        in (c0+r*(c1+r*(c2+r*(c3+r*(c4+r*(c5+r*(c6+r*(c7+r*c8))))))))*(if y<0 then (-1) else 1)
    in ret

let dummyModelOneScen(RNs:[]f64):[][]f64=unflatten numPeriods numItems RNs --form of single scen as input i.e. time x columns

let dummyUseBatchOfScens(scens:[][][]f64):f32=
-- use scensFromArrays function (inner version) here
42 

let dummyBatchedInnerLoop=
    let numBatches=numScens//numScensPerBatch
    let numResults=3--number of values from inner loop e.g. COG1,2,3
    let res:f32=replicate numResults 0
    in loop res'=res for i<numBatches do
        --generate enough RNs for a batch here
        aResult=dummyUseBatchOfScens rnstuff
        res'+.+aResult--build up aray of of results

