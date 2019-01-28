--maths
let real(x:i32):f32=f32.i32(x)
let exp(x:f32):f32=f32.exp(x)
let sqrt(x:f32):f32=f32.sqrt(x)
let log(x:f32):f32=f32.log(x)
let sum1(x:[]f32):f32=reduce (+) 0f32 x
let sum2(x:[][]f32):f32=reduce (+) 0f32 (map sum1 x)
let prod(x:[]f32):f32=reduce (*) 1f32 x

--constants
let zeros1(s:i32):[]f32=
	replicate s 0.0f32
let zeros2 (s1:i32) (s2:i32) :[][]f32=
	replicate s1 (replicate s2 0.0f32)
let zeros3 (s1:i32) (s2:i32) (s3:i32) :[][][]f32=
	replicate s1 (replicate s2 (replicate s3 0.0f32))

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

--two matrices
let (+..+) (x:[][]f32) (y:[][]f32) = map2 (map2 (+)) x y
let (-..-) (x:[][]f32) (y:[][]f32) = map2 (map2 (-)) x y
let (*..*) (x:[][]f32) (y:[][]f32) = map2 (map2 (*)) x y

--Back-recursive reserves; cflow assumed at start month, v is monthly, so we do not use the 1st v
let backDisc (v:[]f32) (PVs:*[]f32) (cflow:[]f32):*[]f32=
    let n=length PVs
    let PVs'=update PVs (n-1) cflow[n-1]
    let (discd,t)= loop (discd':*[]f32,t':i32) = (PVs',(n-1)) while t'>=1i32 do (discd' with [t'-1] = discd'[t']*v[t']+cflow[t'-1],(t'-1))
    in discd
