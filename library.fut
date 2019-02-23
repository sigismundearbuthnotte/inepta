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

--Back-recursive reserves; cflow assumed at start month, v is monthly, so we do not use the 1st v
let backDisc1 (v:[]f32) (PVs:*[]f32) (cflow:[]f32):*[]f32= -- deprecated, does one array at at time - inefficent
    let n=length PVs
    let PVs'=update PVs (n-1) cflow[n-1]
    let (discd,t)= loop (discd':*[]f32,t':i32) = (PVs',(n-1)) while t'>=1i32 do (discd' with [t'-1] = discd'[t']*v[t']+cflow[t'-1],(t'-1))
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
    storeAll
