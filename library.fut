type real=f32
type int=i32

--utilities
let udne(x:*[]f32) (i:i32) (v:f32):(*[]f32)=
    if length x==0 then x else update x i v

--maths
let real(x:i32):f32=f32.i32(x)
let exp(x:f32):f32=f32.exp(x)
let sqrt(x:f32):f32=f32.sqrt(x)
let log(x:f32):f32=f32.log(x)
let sum1(x:[]f32):f32=reduce (+) 0f32 x
let sum2(x:[][]f32):f32=reduce (+) 0f32 (map sum1 x)
let prod(x:[]f32):f32=reduce (*) 1f32 x
let sumprod(x:[]f32)(y:[]f32):f32=sum1 (map2 (*) x y )
let cumsum(x:[]f32):[]f32=scan (+) 0 x
let cumprod(x:[]f32):[]f32=scan (*) 1 x
let maxi=i32.max
let maxr=f32.max
let mini=i32.min
let minr=f32.min

--constants
let zeros1(s:i32):[]f32=
	replicate s 0.0f32
let zeros2 (s1:i32) (s2:i32) :[][]f32=
	replicate s1 (replicate s2 0.0f32)
let zeros3 (s1:i32) (s2:i32) (s3:i32) :[][][]f32=
	replicate s1 (replicate s2 (replicate s3 0.0f32))
let zerosi1(s:i32):[]i32=
	replicate s 0
let undefined:f32=3.14159e20
let undef1(s:i32):[]f32=
	replicate s undefined
let undef2 (s1:i32) (s2:i32) :[][]f32=
	replicate s1 (replicate s2 undefined)

--scalar + vector
let (*.) (x:f32) (y:[]f32) = map (x*) y
let (+.) (x:f32) (y:[]f32) = map (x+) y
let (-.) (x:f32) (y:[]f32) = map (x-) y

--scalar + matrix
let (*..) (x:f32) (y:[][]f32) = map (map (x*)) y
let (+..) (x:f32) (y:[][]f32) = map (map (x+)) y

--two vectors
let (+.+) (x:[]f32) (y:[]f32) = map2 (+) x y
let (-.-) (x:[]f32) (y:[]f32) = map2 (-) x y
let (*.*) (x:[]f32) (y:[]f32) = map2 (*) x y
let (/./) (x:[]f32) (y:[]f32) = map2 (/) x y

--two matrices
let (+..+) (x:[][]f32) (y:[][]f32) = map2 (map2 (+)) x y
let (-..-) (x:[][]f32) (y:[][]f32) = map2 (map2 (-)) x y
let (*..*) (x:[][]f32) (y:[][]f32) = map2 (map2 (*)) x y

--two 3d arrays
let (+...+) (x:[][][]f32) (y:[][][]f32) = map2 (map2 (map2 (+))) x y

--linear algebra
let multMatVec(m:[][]f32)(v:[]f32):[]f32=map (sumprod v) m

--Back-recursive reserves; cflow assumed at start month, v is monthly, so we do not use the 1st v
let backDisc1 (v:[]f32) (PVs:*[]f32) (cflow:[]f32):*[]f32= -- deprecated, does one array at at time - inefficent
    let n=length PVs
    let PVs'=update PVs (n-1) cflow[n-1]
    let (discd,_)= loop (discd':*[]f32,t':i32) = (PVs',(n-1)) while t'>=1i32 do (discd' with [t'-1] = discd'[t']*v[t']+cflow[t'-1],(t'-1))
    in discd

--2 arrays; pass store-all in plus rows thereof to alter.  NB: overwites its source
let backDisc2 [n] (storeAll:*[][n]f32) (inds:[]i32) (v:[][]f32) :*[][n]f32=
    let i1=inds[0]
    let i2=inds[mini 1 (length(inds)-1)]
    let discd=
    if n==0 then 
        [] 
    else
        let (d,_)=
        loop (discd':*[][]f32,t':i32) = (storeAll,(n-1)) while t'>=1i32 do 
            let disc2=discd' with [i1,t'-1] = discd'[i1,t'-1]+discd'[i1,t']*v[i1,t']
            let disc3=if length(inds)==2 then disc2 with [i2,t'-1] = disc2[i2,t'-1]+disc2[i2,t']*v[i2,t'] else disc2
            in (disc3,(t'-1))
        in d
    in discd

--max 3 arrays; pass store-all in plus rows thereof to alter  NB: overwites its source
let backDisc4 [n] (storeAll:*[][n]f32) (inds:[]i32) (v:[][]f32) :*[][n]f32=
    let i1=inds[0]
    let i2=inds[mini 1 (length(inds)-1)]
    let i3=inds[mini 2 (length(inds)-1)]
    let i4=inds[mini 3 (length(inds)-1)]
    let discd=
    if n==0 then 
        [] 
    else
        let (d,_)=
        loop (discd':*[][]f32,t':i32) = (storeAll,(n-1)) while t'>=1i32 do 
            let disc2=discd' with [i1,t'-1] = discd'[i1,t'-1]+discd'[i1,t']*v[i1,t']
            let disc3=if length(inds)>=2 then disc2 with [i2,t'-1] = disc2[i2,t'-1]+disc2[i2,t']*v[i2,t'] else disc2
            let disc4=if length(inds)>=3 then disc3 with [i3,t'-1] = disc3[i3,t'-1]+disc3[i3,t']*v[i3,t'] else disc3
            let disc5=if length(inds)>=4 then disc4 with [i4,t'-1] = disc4[i4,t'-1]+disc4[i4,t']*v[i4,t'] else disc4
            in (disc5,(t'-1))
        in d
    in discd

--just calculate single discounted value hence use sumprod - simpler (and hopefully more efficient than a loop)  NB: overwites its source
let backDiscSingle1 [n] (storeAll:*[][n]f32) (ind:i32) (v:[][]f32) (t:i32)   :*[][n]f32=
    storeAll with [ind,t]= sumprod  storeAll[ind,t:] v[ind,t:]

let backDiscSingle3 [n] (storeAll:*[][n]f32) (inds:[]i32) (v:[][]f32) (t:i32)   :*[][n]f32=
    let i1=inds[0]
    let i2=inds[mini 1 (length(inds)-1)]
    let i3=inds[mini 2 (length(inds)-1)]
    let sa1=storeAll with [i1,t]= (sumprod  storeAll[i1,t:] v[i1,t:])  
    let sa2= if length(inds)>=2 then sa1 with [i2,t]= (sumprod  sa1[i2,t:] v[i2,t:]) else sa1  
    let sa3 = if length(inds)>=3 then sa2 with [i3,t]= (sumprod  sa2[i3,t:] v[i3,t:])  else sa2
    in sa3

let interp [n] (storeAll:*[][n]f32) (indSource:i32)  (indTarget:i32) :*[][n]f32= --this is a dummy: it's supposed to interpolate indSource and place the result in indTarget
    storeAll with [indTarget]=(copy storeAll[indSource])

--MT based on mt19937ar.c by Nishimura and Matsumoto (2002)
--Generate RNs in blocks of 624 (with differing seeds, of course) run in parallel; how many blocks and how many times we iterate each and every block is user-defined
let N:i32=624
let M:i32=397
let MATRIX_A:u32=0X9908b0df
let UPPER_MASK:u32=0X80000000
let LOWER_MASK:u32=0X7fffffff
let maxInt:u32=2**32-1
let maxIntF:f64=f64.u32 maxInt

--initialise 1 block of 624 (one seed)
let initMT(s:u32):[N]u32=
    let ret:*[N]u32=[s]++(replicate (N-1) 0u32)
in loop ret':*[N]u32=ret for i<(N-1) do ret' with [i+1]=1812433253u32*(ret'[i]^(ret'[i]>>30))+(u32.i32 i)+1u32

--return next states and RNs
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

--statistical
let mean(x:[]f32):f32=(sum x)/(length X)
let stdErr(x:[]32):f32=
    mean( x *.* x) - (mean x)**2
let stdErrAntithetic=stdErr--TODO
