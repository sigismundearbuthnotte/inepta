--takes all the RNs, sufficient for all (assumed to be standard IID Normals, FTB) as one big vector and returns [][][]f32, as one would expect from the outer scens
--currently it returns equity monthly returns (with stochastic interest rates) but not the YC
--the returned value is wrong as there's no quadratic variation bit
let BS_2fHW (numScens:i32) (numPeriods:i32) (params:([2]f32,[2]f32,f32,[]f32,[]f32,[][]f32)) (RNs:[]f32):[][][]f32=
    let alpha:[2]f32=params.1
    let sigma:[2]f32=params.2
    let rho=params.3--actually, will be implicit in chol but needed anyway
    let ycStart:[]f32=params.4
    let chol:[][]f32=params.6--lower triangular
    let eqSigmas:[]f32=params.5
    let RNsPerPeriod=length (chol[0])--must have this

    let np=2*numPeriods
    let periods=(map real (iota np))
    let periodsi=iota numPeriods
    let expa=map (\x->exp (-1*alpha[0]*x/12)) periods
    let expb=map (\x->exp (-1*alpha[1]*x/12)) periods
    let exp2a=map (\x->x*x) expa
    let exp2b=map (\x->x*x) expb
    let inva=1f32/alpha[0]
    let invb=1f32/alpha[1]
    let invab=1f32/(alpha[0]+alpha[1])
    let v=(sigma[0]*sigma[0]*inva*inva)*.((-1.5f32*inva)+.periods+.+(2f32*inva)*.expa-.-(0.5f32*inva)*.exp2a) +.+
        (sigma[1]*sigma[1]*invb*invb)*.((-1.5f32*invb)+.periods+.+(2f32*invb)*.expb-.-(0.5f32*invb)*.exp2b) +.+
        (2*rho*sigma[0]*sigma[1]*inva*invb)*.(periods+.+inva*.(-1+.expa)+.+invb*.(-1+.expb)-.-invab*.(-1+.expa*.*expb))
    let aexp=inva*.(1-.expa)
    let bexp=invb*.(1-.expb)
    let logyc(t:i32)(x:f32)(y:f32):[]f32=
        (map (\(i:i32):f32->0.5*(v[i]-v[t+i]-v[t])) periodsi)-.-x*.aexp-.-y*.bexp
    let yc(t:i32)(x:f32)(y:f32):[]f32=(1f32/ycStart[t])*.ycStart[t:t+numPeriods]*.*(map exp (logyc t x y))
    let sqrt12=(1f32/12.0f32)**0.5
    let it24:f32=1f32/24f32
    let expIntegralPhi=map (\(t:i32)->ycStart[t+1]/ycStart[t]*(exp (-0.5*(v[t+1]-v[t]))) ) periodsi--element i integrates from i/12 to (i+1)/12

    let BS_2fHWoneScen (RNs:[][]f32):[][]f32=
        let corrRNs=map (multMatVec chol) RNs
        let xs=[0f32]++scan (\(x:f32) (w:f32)->sqrt12*w-alpha[0]*x) 0f32 corrRNs[:,0]
        let ys=[0f32]++scan (\(x:f32) (w:f32)->sqrt12*w-alpha[1]*x) 0f32 corrRNs[:,1]
        let ycs=map3 yc periodsi xs ys
        let expIntegralR=expIntegralPhi*.*(map exp (it24*.((tail xs)+.+(tail ys)+.+ xs[:numPeriods]+.+ys[:numPeriods])))
        let eqRets=map2 (*.) expIntegralR (map (eqSigmas *.* ) corrRNs[:,2:])--this IS wrong!!! - NO ITO TERM - can't remember how to do it for multi-d
    in eqRets

    --antithetes - every model is required to do this
    -- do not know if it is better to do 2 runs or one run over all RNs (original and antis)
    let RNs'=unflatten_3d (numScens//2) numPeriods RNsPerPeriod RNs
    let res1=map BS_2fHWoneScen RNs'
    let RNs''=unflatten_3d (numScens//2) numPeriods RNsPerPeriod (map (0-) RNs)
    let res2=map BS_2fHWoneScen RNs''
in res1++res2

