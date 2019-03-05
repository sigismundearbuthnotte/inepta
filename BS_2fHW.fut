--dummy file for an inner model
--takes all the RNs, sufficient for all (assumed to be standard IID Normals, FTB) as one big vector and returns [][][]f32, as one would expect from the outer scens
let BS_2fHWoneScen (numPeriods:i32) (alpha:[]f32) (sigma:[]f32) (nu:[]f32) (ycStart:[]f32) (chol:[][]f32) (RNs:[][]f32):[][]f32=
    RNs

let BS_2fHW (numScens:i32) (numPeriods:i32) (params:([2]f32,[2]f32,[2]f32,[]f32,[][]f32)) (RNs:[]f32):[][][]f32=
    let alpha:[2]f32=params.1
    let sigma:[2]f32=params.2
    let nu:[2]f32=params.3
    let ycStart:[]f32=params.4
    let chol:[][]f32=params.5--lower triangular
    let RNsPerPeriod=length (chol[0])
    let RNs'=unflatten_3d numScens numPeriods RNsPerPeriod RNs[:RNsPerPeriod*numPeriods*numScens]--remove excess RNs so as to unflatten
    --etc
    in map (BS_2fHWoneScen numPeriods alpha sigma nu ycStart chol) RNs'
