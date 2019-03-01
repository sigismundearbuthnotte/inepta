--Template for batched inner scens
--Generate RNs in blocks of 624 (with differing seeds, of course) run in parallel; how many blocks and how many times we iterate each and every block is user-defined

--MT based on mt19937ar.c by Nishimura and Matsumoto (2002)
let numRNsPerPeriod:i32=20--for the sake of argument
let numPeriods:i32=300
let numItems=20
let numRNsPerScen=numRNsPerPeriod*numPeriods
let numScens:i32=10000
let numScensPerBatch:i32=1000--ftsoa
let numRNsPerBatchOfScens=numRNsPerScen*numScensPerBatch
let numMTItersPerBatch:i32=10--ftsoa; i.e. how many ierations do we run the MT
let numBlocksOf624PerBatch:i32=1+numRNsPerBatchOfScens//(624*numMTItersPerBatch)--let's assume it doesn't divide exactly
let seeds:[]u32=5984...(5984+(u32.i32 numBlocksOf624PerBatch-1))
let maxInt:u32=2**32-1
let maxIntF:f64=f64.u32 maxInt
let (+.+) (x:[]f32) (y:[]f32) = map2 (+) x y

let N:i32=624
let M:i32=397
let MATRIX_A:u32=0X9908b0df
let UPPER_MASK:u32=0X80000000
let LOWER_MASK:u32=0X7fffffff

let initMT(s:u32):[N]u32=
    let ret:*[N]u32=[s]++(replicate (N-1) 0u32)
in loop ret':*[N]u32=ret for i<(N-1) do ret' with [i+1]=1812433253u32*(ret'[i]^(ret'[i]>>30))+(u32.i32 i)+1u32

let initStatesOf624:[][]u32=map initMT seeds

let nextBlockOf624 (b:[]u32):([]u32,[]f64)=
    let y =map2 (|) (map (&UPPER_MASK) b[0:N-M]) (map (&LOWER_MASK) b[1:N-M+1])
    let b1=map2 (^) (map2 (^) b[M:] (map (>>1) y)) (map (\x->if x&1u32==0 then 0 else MATRIX_A) y)

    let b1'= b[N-M:2*(N-M)]
    let y' =map2 (|) (map (&UPPER_MASK) b1') (map (&LOWER_MASK) b[N-M+1:2*(N-M)+1])
    let b2=map2 (^) (map2 (^) b1[:N-M] (map (>>1) y')) (map (\x->if x&1u32==0 then 0 else MATRIX_A) y')

    let y'' =map2 (|) (map (&UPPER_MASK) b[2*(N-M):N-1]) (map (&LOWER_MASK) b[2*(N-M)+1:])
    let b3=map2 (^) (map2 (^) b2[:2*M-N-1] (map (>>1) y'')) (map (\x->if x&1u32==0 then 0 else MATRIX_A) y'')

    let y''=(b[N-1]&UPPER_MASK)|(b1[0]&LOWER_MASK)
    let b4=b2[2*M-1-N]^(y''>>1)^(if y''&1u32==0 then 0 else MATRIX_A)

    let temperTemper(y:u32):u32=
        let y1=y^(y>>11)
        let y2=y1^((y1<<7)&0X9d2c5680)
        let y3=y2^((y2<<15)&0Xefc60000)
        in y3^(y3>>18)

    let b5=b1++b2++b3++[b4]
in (b5,map (temperTemper >-> f64.u32 >-> (/maxIntF)) b5)

--see Glasserman p68
let BSMNormInv(x:f64)=
    let a0:f64=2.50662823884
    let a1:f64=(-18.61500062529)
    let a2:f64=41.39119773534
    let a3:f64=(-25.44106049637)
    let b0:f64=(-8.47351093090)
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
        let r'=if y<=0 then x else 1-x
        let r=f64.log(-f64.log r')
        in (c0+r*(c1+r*(c2+r*(c3+r*(c4+r*(c5+r*(c6+r*(c7+r*c8))))))))*(if y<0 then (-1) else 1)
    in ret

let dummyMultiDExpBrownianMotion(RNs:[]f64):[][][]f32=
    unflatten_3d 1 1 1 (map f32.f64 RNs)

let dummyModelOneScen(RNs:[]f64):[][]f64=unflatten numPeriods numItems RNs --form of single scen as input i.e. time x columns

let dummyUseBatchOfScens(scens:[][][]f32):[]f32=
-- use scensFromArrays function (inner version) here and do some kind of pricing Monte Carlo
[42,42,42]

--do e.g. 1000 scens at a time for total of 10k scens - e.g. if the RNs for all scens would take up too much memory
let dummyBatchedInnerLoop:[]f32=
    let numBatches=numScens//numScensPerBatch
    let numBatchesR=f32.i32 numBatches
    let numResults=3--number of values from inner loop e.g. COG1,2,3
    let res:[]f32=replicate numResults 0
    --loop through batches of scens
    let (res'',_)=
    loop (res',statesOf624')=(res,initStatesOf624) for i<numBatches do
        let (statesOf624'',RNs) = unzip (map nextBlockOf624 statesOf624')
        let scens=dummyMultiDExpBrownianMotion (flatten RNs)
        let aResult=dummyUseBatchOfScens scens
        let res''=res'+.+aResult--build up aray of of results from the batches
        in (res'',statesOf624'')
in map (/numBatchesR) res'' --assuming the results are means, so the true mean needs dividing by the number of batches

let testURNs(seed:u32):[]f64=
    let state=initMT seed
    let (s1,b1) = nextBlockOf624 state
    let (_,b2) = nextBlockOf624 s1
in b1++b2

let testInvNormCDF:[]f64=
    map BSMNormInv [0.00001f64,0.0001f64,0.001f64,0.01f64,0.1f64,0.5f64,0.9f64,0.99f64,0.999f64,0.9999f64,0.99999f64]

let main:[]f64=
    --let r1=testURNs 9947
    --in reduce (+) 0 r1
testInvNormCDF