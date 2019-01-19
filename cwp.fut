--library utilities
let real(x:i32):f32=f32.i32(x)

let exp(x:f32):f32=f32.exp(x)

let sqrt(x:f32):f32=f32.sqrt(x)

let log(x:f32):f32=f32.log(x)

let sum(x:[]f32):f32=reduce (+) 0f32 x

let zeros1(s:i32):[]f32=

	replicate s 0.0f32

let zeros2 (s1:i32) (s2:i32) :[][]f32=

	replicate s1 (replicate s2 0.0f32)

let zeros3 (s1:i32) (s2:i32) (s3:i32) :[][][]f32=

	replicate s1 (replicate s2 (replicate s3 0.0f32))

-- Black Scholes
let ND (x:f32) :f32 = -- positive values of x only
    let gamma=0.33267f32
    let a1=0.4361836f32
    let a2 = -0.1201676f32
    let a3=0.937298f32
    let inv_sqrt_2pi=0.39894228f32
    let k=1.0f32/(1.0f32+gamma*x)
    let nd=inv_sqrt_2pi*(exp (-x*x*0.5f32)) 
    in 1.0f32-nd*(((a3*k+a2)*k+a1)*k)

let normsDist (x:f32) :f32 = -- cumulative Normal
    if x>=0.0f32 then (ND (x))  else 1.0f32-(ND (-x)) 

let putOption(s:f32) (k:f32) (r:f32) (t:f32) (sigma:f32) :f32 = 
    let sig_sqrt_t=sigma*(sqrt (t)) 
    let d1=((log (s/k)) +(r+0.5f32*sigma*sigma)*t)/sig_sqrt_t
    let d2=d1-sig_sqrt_t
    in k*(exp (-r*t)) *(normsDist (-d2)) -s*(normsDist (-d1)) 

--data record
type data_cwp={
polID:i32,
prod:i32,
ageYears:i32,
ageMonths:i32,
termOS:i32,
sex:i32,
fundID:i32,
elapsed_period:i32,
sumAssured:f32,
revBonus:f32,
premMonthly:f32,
assetShare:f32
}

-- state by defintion is carried forward so the previous value of state will also always be of this type
type state_cwp={
termO_S:i32,
cflow:f32,
reserveCF:f32,
revBonusCF:f32,
survCF:f32,
assetShareCF:f32,
ageYrs:i32,
ageMths:i32,
COG:f32,
COG2:[5]f32,
COGDiff:[5]f32,
COG3:[2][3][3]f32,
pvCOG:f32,
dBen:f32
}

-- values from before t-1 (any number of these types, as required)
type state_cwp__2={
    dBen:f32
}

-- intermediate "columns" i.e. reused in a period's calculations, but not needed for state nor for outside reporting
type state_cwp_inter={
   qxMonthly:f32,
   lapseRateMonthly:f32,
   gteeBen:f32
}

-- not needed for state but required outside; a logical (if not practical) distinction from intermediate
type state_cwp_results={
    cflow:f32
}

-- all states to make up the total state
type state_cwp_all={
    state__2: state_cwp__2,
    state__1:state_cwp,
    intermediate: state_cwp_inter,
    results: state_cwp_results,
    state_new:state_cwp,
    t:i32
}

let dataFromArrayscwp [nr] (dataInt:[nr][]i32) (dataFloat:[nr][]f32) : []data_cwp=
    let tuplesI = map (\x->(x[0],x[1],x[2],x[3],x[4],x[5],x[6],x[7])) dataInt
    let tuplesF = map (\x->(x[0],x[1],x[2],x[3])) dataFloat
    in map2 (\x y :data_cwp->{polID=x.1,prod=x.2,ageYears=x.3,ageMonths=x.4,termOS=x.5,sex=x.6,fundID=x.7,elapsed_period=x.8,sumAssured=y.1,revBonus=y.2,premMonthly=y.3,assetShare=y.4}) tuplesI tuplesF

let main [numPols] (fileDataInt:[numPols][]i32) (fileDataReal:[numPols][]f32) (numPeriods:i32) (table_deathRates:[][]f32) (table_lapseRates:[][]f32) (table_revBonusRateMonthly:[][]f32) (table_renExpsMonthly:[][]f32) (table_surrPropnAssetShare:[][]f32) (table_matyPropnAssetShare:[]f32) :[][]f32 = 
    -- read data
    unsafe 
    let data_cwp=dataFromArrayscwp fileDataInt fileDataReal

    -- initialisation function (TODO reinsert derived-data-based calculations)
    let init_cwp (d:data_cwp) :state_cwp=
        let initCOG=1234.0f32
        let termO_S=d.termOS  
        let cflow=0.0f32  
        let reserveCF=d.assetShare+initCOG  
        let revBonusCF=d.revBonus  
        let survCF=1.0f32  
        let assetShareCF=d.assetShare  
        let ageYrs=d.ageYears  
        let ageMths=d.ageYears*12i32+d.ageMonths  
        let v=0.2f32
        let rfr=0.05f32
        let tt=(real (d.termOS))   
        let COG=putOption d.assetShare ((d.sumAssured+d.revBonus)*table_matyPropnAssetShare[d.prod]) rfr tt v
        let volAdjs=[-0.02f32,-0.01f32,0.0f32,0.01f32,0.02f32]  
        let COG2 = map (putOption d.assetShare ((d.sumAssured+d.revBonus)*table_matyPropnAssetShare[d.prod]) rfr tt) (map2 (+) (replicate 5 v) volAdjs)
        let pvCOG=0.0f32  
        let dBen=0.0f32  
        let COGDiff = zeros1 5
        let COG3 = zeros3 2 3 3
        in {termO_S=termO_S,cflow=cflow,reserveCF=reserveCF,revBonusCF=revBonusCF,survCF=survCF,assetShareCF=assetShareCF,ageYrs=ageYrs,ageMths=ageMths,COG=COG,COG2=COG2,COGDiff=COGDiff,COG3=COG3,pvCOG=pvCOG,dBen=dBen}

    -- define run function
    let runOnePol (p:data_cwp) :[]f32 = 

        -- initialisation of state from data
        let init_state_cwp = init_cwp p

        -- initial value of all-state
        --should be able to get away with structural typing: no need to name fields
        let init_all_state:state_cwp_all = {
            state__2 = {dBen=0f32},
            state__1=init_state_cwp,
            intermediate={gteeBen=0f32,qxMonthly=0f32,lapseRateMonthly=0f32},
            results={cflow=0f32},
            state_new=init_state_cwp, -- do not care what the values are so reuse initial values
            t=1i32
        }

        -- state transition functions (columns)

        let volAdjs=[-0.02f32,-0.01f32,0.0f32,0.01f32,0.02f32]  -- not a function at all

        let COG3(as: state_cwp_all): state_cwp_all =
            let arrFn3 (index2:i32)  (index1:i32)  (index0:i32)  : f32 = 
            let x=1i32  
            in (real (x+index0+index1+index2))   
            let arrFn4 ( index2:i32 ) ( index1:i32 ) : []f32 =  map3 (\ x1  x2  x3 ->arrFn3 x1  x2  x3 )  (iota 3i32 )  [index2]  [index1] 
            let arrFn5 ( index2:i32 ) : [][]f32 =  map2 (\ x1  x2 ->arrFn4 x1  x2 )  (iota 3i32 )  [index2] 
            let COG3res =  map (\ x1 ->arrFn5 x1 )  (iota 2i32 ) in
            as with state_new.COG3=COG3res

        let termO_S(as: state_cwp_all): state_cwp_all =
            as with state_new.termO_S = as.state__1.termO_S-1i32  

        let ageMths(as: state_cwp_all): state_cwp_all =
            as with state_new.ageMths=as.state__1.ageMths+1i32  

        let ageYrs(as: state_cwp_all): state_cwp_all =
            as with state_new.ageYrs=as.state_new.ageMths//12i32  

        let monthlyRates(as: state_cwp_all): state_cwp_all =  -- common calculation "returning" two "columns"
            let adj=1i32+2i32*3i32 -- something complicated in common  
            let as1 = as with intermediate.qxMonthly=table_deathRates[as.state_new.ageYrs+adj,p.sex] --Table lookup mechansim needs revisiting!
            in as1 with intermediate.lapseRateMonthly=table_lapseRates[p.prod,p.sex]

        let survCF(as: state_cwp_all): state_cwp_all =
            as with state_new.survCF = as.state__1.survCF*(1.0f32-as.intermediate.qxMonthly-as.intermediate.lapseRateMonthly)  

        let cflow(as: state_cwp_all): state_cwp_all =
            as with results.cflow = as.state__1.survCF*(p.premMonthly-table_renExpsMonthly[p.prod,0i32])-as.intermediate.qxMonthly*as.state__1.dBen-as.intermediate.lapseRateMonthly*as.state__1.assetShareCF*table_surrPropnAssetShare[p.prod,0i32]

        let revBonusCF(as: state_cwp_all): state_cwp_all =
            as with state_new.revBonusCF = as.state__1.revBonusCF*(1f32+table_revBonusRateMonthly[p.prod,0i32]) 

        let assetShareCF(as: state_cwp_all): state_cwp_all =
            as with state_new.assetShareCF = as.state__1.assetShareCF+as.results.cflow

        let gteeBen(as: state_cwp_all): state_cwp_all =
            as with intermediate.gteeBen=as.state_new.survCF*(p.sumAssured+as.state_new.revBonusCF)  

        let COG(as: state_cwp_all): state_cwp_all =
            let v=0.2f32 --TODO ESG, even for serial?
            let rfr=0.05f32
            let tt=((real (p.termOS-as.t)) )  
            in as with state_new.COG = putOption as.state_new.assetShareCF as.intermediate.gteeBen rfr tt v

        let dBen(as: state_cwp_all): state_cwp_all =
            as with state_new.dBen=
                if as.intermediate.gteeBen>as.state_new.assetShareCF then  
                    as.intermediate.gteeBen  
                else  
                    as.state_new.assetShareCF  

        let COG2(as: state_cwp_all): state_cwp_all = --TODO this is a simplificaion of the generated array function - should we alter the code gen to do this?
            let rfr=0.05f32
            let tt=real (p.termOS-as.t)
            in as with state_new.COG2 = map (putOption as.state_new.assetShareCF as.intermediate.gteeBen rfr tt)  (map2 (+) volAdjs (replicate 5 0.2f32))

        let COGDiff(as: state_cwp_all): state_cwp_all =
            as with state_new.COGDiff = (map2 (-) as.state_new.COG2 as.state__1.COG2)

        let reserveCF(as: state_cwp_all): state_cwp_all =
            as with state_new.reserveCF = as.state_new.assetShareCF+as.state_new.COG  

        -- One period: pipeline transitions and storage
        let runOnePeriod(as: state_cwp_all): state_cwp_all=
            as |> COG3 |> termO_S |> ageMths |> ageYrs |> monthlyRates |> survCF |> cflow |> revBonusCF |> assetShareCF |>gteeBen |>
                COG |> dBen |> COG2 |> COGDiff

        -- Store results for next period
        let store(as: state_cwp_all): state_cwp_all = 
        {
            state__2 = {dBen=as.state__1.dBen},
            state__1 = as.state_new, -- this is the only really important one!
            intermediate = as.intermediate,
            results= as.results,
            state_new = as.state_new,
            t=as.t+1
        }

        -- time loop
        let runAllPeriods = iterate numPeriods (runOnePeriod>->store)

        -- finalisation (TODO currently only the identity)
        let runFinalise(as: state_cwp_all): state_cwp_all=
            as

        -- final state TODO final as in maturity
        let final_all_state = (runAllPeriods >-> runFinalise) init_all_state

        --return results
        let res=[final_all_state.results.cflow]

        -- TODO anything special required for PVs?

        in res
    
    -- map run to data
    let allRes = map runOnePol data_cwp

    -- extract results

    -- reduce results (sum)

    in allRes