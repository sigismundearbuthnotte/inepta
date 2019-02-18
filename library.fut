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
let interp(x:[]f32):[]f32=x -- this is a dummy
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

--2 arrays; pass store-all in plus rows thereof to alter
let backDisc2 [n] (cflow:*[][n]f32) (v:[][]f32) (inds:[]i32) :*[][n]f32=
    let i1=inds[0]
    let i2=inds[1]
    let discd=
    if n==0 then 
        [] 
    else
        let (d,_)=
        loop (discd':*[][]f32,t':i32) = (cflow,(n-1)) while t'>=1i32 do 
            let disc2=discd' with [i1,t'-1] = discd'[i1,t'-1]+discd'[i1,t']*v[i1,t']
            let disc3=disc2 with [i2,t'-1] = disc2[i2,t'-1]+disc2[i2,t']*v[i2,t']
            in (disc3,(t'-1))
        in d
    in discd

let backDisc3 [n] (cflow:*[][n]f32) (v:[][]f32):*[][n]f32=
    let discd=
    if n==0 then 
        [] 
    else
        let (d,_)=
        loop (discd':*[][]f32,t':i32) = (cflow,(n-1)) while t'>=1i32 do 
            let disc2=discd' with [0,t'-1] = discd'[0,t'-1]+discd'[0,t']*v[0,t']
            let disc3=disc2 with [1,t'-1] = disc2[1,t'-1]+disc2[1,t']*v[1,t']
            let disc4=disc3 with [2,t'-1] = disc3[1,t'-1]+disc3[1,t']*v[2,t']
            in (disc4,(t'-1))
        in d
    in discd
