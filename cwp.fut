--library utilities
let (*.) (x:f32) (y:[]f32) = map (x*) y
let (*..) (x:f32) (y:[][]f32) = map (map (x*)) y
let (+.) (x:f32) (y:[]f32) = map (x+) y
let (+..) (x:f32) (y:[][]f32) = map (map (x+)) y
let (+.+) (x:[]f32) (y:[]f32) = map2 (+) x y
let (+..+) (x:[][]f32) (y:[][]f32) = map2 (map2 (+)) x y
let (-.-) (x:[]f32) (y:[]f32) = map2 (-) x y
let (-..-) (x:[][]f32) (y:[][]f32) = map2 (map2 (-)) x y
let (*.*) (x:[]f32) (y:[]f32) = map2 (*) x y
let (*..*) (x:[][]f32) (y:[][]f32) = map2 (map2 (*)) x y

let backDisc (v:[]f32) (PVs:*[]f32) (cflow:[]f32):*[]f32=
    --Back-recursive reserves; cflow assumed at start month, v is monthly, so we do not use the 1st v
    let n=length PVs
    let PVs'=update PVs (n-1) cflow[n-1]
    let (discd,t)= loop (discd':*[]f32,t':i32) = (PVs',(n-1)) while t'>=1i32 do (discd' with [t'-1] = discd'[t']*v[t']+cflow[t'-1],(t'-1))
    in discd

let real(x:i32):f32=f32.i32(x)

let exp(x:f32):f32=f32.exp(x)

let sqrt(x:f32):f32=f32.sqrt(x)

let log(x:f32):f32=f32.log(x)

let sum(x:[]f32):f32=reduce (+) 0f32 x

let sumProd(x:[]f32,y:[]f32):f32 = sum (map2 (*) x y)

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
    let s2=f32.max s 1f32 --hack!
    let sig_sqrt_t=sigma*(sqrt (t)) 
    let d1=((log (s2/k)) +(r+0.5f32*sigma*sigma)*t)/sig_sqrt_t
    let d2=d1-sig_sqrt_t
    in k*(exp (-r*t)) *(normsDist (-d2)) -s2*(normsDist (-d1)) 

let maxPeriods=600i32
let maxBases=10i32

--data record.  These do not have to have the types grouped but it makes life slightly easier when converting the input data arrays 
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

let data_cwp_numInt=8i32
let data_cwp_numFloat=4i32

-- state by defintion is carried forward so the previous value of state will also always be of this type
type state_cwp={
termO_S:i32,
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
dBen:f32,
discFac:f32,
discdCflow:f32
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

-- not needed for state but required outside; a logical (if not practical) distinction from intermediate.  User specifies these?
type state_cwp_results={
    cflow:f32
}

type state_cwp__999={
    survCF:[]f32, -- here's another one, used for adjusting proxies.  TODO? separate both of these out into their own structures? (1)Rebased and (2)Proxy items
    cflow:[]f32 -- for backsum-discounting
}

-- all states to make up the total state
type state_cwp_all={
    p:data_cwp,
    state__999: state_cwp__999,
    state__2: state_cwp__2,
    state__1:state_cwp,
    intermediate: state_cwp_inter,
    results: state_cwp_results,
    state_new:state_cwp,
    t:i32,
    forceTheIssue:f32,
    reserves:[][]f32, --this might refer to anything extracted from a non-experience basis (and there might be >1 of these).  Needs to be soft.
    basisNum:i32
}

let dataFromArrayscwp [nr] (dataInt:[nr][data_cwp_numInt]i32) (dataFloat:[nr][data_cwp_numFloat]f32) : []data_cwp=
    let tuplesI = map (\x->(x[0],x[1],x[2],x[3],x[4],x[5],x[6],x[7])) dataInt
    let tuplesF = map (\x->(x[0],x[1],x[2],x[3])) dataFloat
    in map2 (\x y :data_cwp->{polID=x.1,prod=x.2,ageYears=x.3,ageMonths=x.4,termOS=x.5,sex=x.6,fundID=x.7,elapsed_period=x.8,sumAssured=y.1,revBonus=y.2,premMonthly=y.3,assetShare=y.4}) tuplesI tuplesF

let main [numPols][numBases][numPeriods] (fileDataInt:[numPols][data_cwp_numInt]i32) (fileDataReal:[numPols][data_cwp_numFloat]f32) (doRebase:[numBases]bool) (isRebaseTime:[numPeriods]bool) (table_deathRates:[][]f32) (table_lapseRates:[][]f32) (table_revBonusRateMonthly:[][]f32) (table_renExpsMonthly:[][]f32) (table_surrPropnAssetShare:[][]f32) (table_matyPropnAssetShare:[][]f32)  (table_disc:[][]f32):[][]f32 = 
    -- read data
    unsafe --probably (we hope) needed only because table reads are "unsafe"
    let data_cwp=dataFromArrayscwp fileDataInt fileDataReal
    let numRebased = length(filter (id) doRebase) 
    let numProxies = length(filter (id>->(!)) doRebase) 

    --for convenience
    let zerosArray=zeros1 numPeriods

    -- initialisation function (TODO reinsert derived-data-based calculations) this function is local as it needs access to tables
    let init_cwp (d:data_cwp) :state_cwp=
        let initCOG=1234.0f32
        let termO_S=d.termOS  
        let reserveCF=d.assetShare+initCOG  
        let revBonusCF=d.revBonus  
        let survCF=1.0f32  
        let assetShareCF=d.assetShare  
        let ageYrs=d.ageYears  
        let ageMths=d.ageYears*12i32+d.ageMonths  
        let v=0.2f32
        let rfr=0.05f32
        let tt=(real (d.termOS))   
        let COG=putOption d.assetShare ((d.sumAssured+d.revBonus)*table_matyPropnAssetShare[d.prod,0]) rfr tt v
        let volAdjs=[-0.02f32,-0.01f32,0.0f32,0.01f32,0.02f32]  
        let COG2 = map (putOption d.assetShare ((d.sumAssured+d.revBonus)*table_matyPropnAssetShare[d.prod,0]) rfr tt) (v +. volAdjs)
        let pvCOG=0.0f32  
        let dBen=0.0f32  
        let COGDiff = zeros1 5
        let COG3 = zeros3 2 3 3
        let discdCflow=0f32
        let discFac=1f32
        in {termO_S=termO_S,reserveCF=reserveCF,revBonusCF=revBonusCF,survCF=survCF,assetShareCF=assetShareCF,ageYrs=ageYrs,ageMths=ageMths,COG=COG,COG2=COG2,COGDiff=COGDiff,COG3=COG3,pvCOG=pvCOG,dBen=dBen,discdCflow=discdCflow,discFac=discFac}

    -- state transition functions (columns)

    let volAdjs=[-0.02f32,-0.01f32,0.0f32,0.01f32,0.02f32]  -- not a function at all, could go to intermediate

    let COG3(as: state_cwp_all): state_cwp_all = --TODO generation of this to be redone as it is now done using Currying
        let arrFn3 (index1:i32)  (index2:i32)  (index3:i32)  : f32 = 
            let x=1i32  
            in (real (x+index1+index2+index3))   
        let arrFn4 ( index1:i32 ) ( index2:i32 ) : []f32 =  map (arrFn3 index1 index2) (iota 3i32 )  
        let arrFn5 ( index1:i32 ) : [][]f32 =  map (arrFn4 index1)  (iota 3i32 )  
        let COG3res =  map arrFn5  (iota 2i32 ) in
        as with state_new.COG3=COG3res

    let termO_S(as: state_cwp_all): state_cwp_all =
        as with state_new.termO_S = as.state__1.termO_S-1i32  

    let ageMths(as: state_cwp_all): state_cwp_all =
        as with state_new.ageMths=as.state__1.ageMths+1i32  

    let ageYrs(as: state_cwp_all): state_cwp_all =
        as with state_new.ageYrs=as.state_new.ageMths//12i32  

    let monthlyRates(as: state_cwp_all): state_cwp_all =  -- common calculation "returning" two "columns"
        let adj=1i32+2i32*3i32 -- something complicated in common  
        let as1 = as with intermediate.qxMonthly=table_deathRates[as.state_new.ageYrs+adj,as.basisNum] --Table lookup mechansim needs revisiting!
        in as1 with intermediate.lapseRateMonthly=table_lapseRates[as.p.prod,as.basisNum]

    let survCF(as: state_cwp_all): state_cwp_all =
        as with state_new.survCF = as.state__1.survCF*(1.0f32-as.intermediate.qxMonthly-as.intermediate.lapseRateMonthly)  

    let cflow(as: state_cwp_all): state_cwp_all =
        as with results.cflow = as.state__1.survCF*(as.p.premMonthly-table_renExpsMonthly[as.p.prod,as.basisNum])-as.intermediate.qxMonthly*as.state__1.dBen-as.intermediate.lapseRateMonthly*as.state__1.assetShareCF*table_surrPropnAssetShare[as.p.prod,as.basisNum]

    let discFac(as: state_cwp_all): state_cwp_all =
        as with state_new.discFac = as.state__1.discFac/(1f32+table_disc[as.t,as.basisNum])

    let discdCflow(as: state_cwp_all): state_cwp_all =
        as with state_new.discdCflow = as.state__1.discdCflow + as.results.cflow*as.state__1.discFac

    let revBonusCF(as: state_cwp_all): state_cwp_all =
        as with state_new.revBonusCF = as.state__1.revBonusCF*(1f32+table_revBonusRateMonthly[as.p.prod,as.basisNum]) 

    let assetShareCF(as: state_cwp_all): state_cwp_all =
        as with state_new.assetShareCF = as.state__1.assetShareCF+as.results.cflow

    let gteeBen(as: state_cwp_all): state_cwp_all =
        as with intermediate.gteeBen=as.state_new.survCF*(as.p.sumAssured+as.state_new.revBonusCF)  

    let COG(as: state_cwp_all): state_cwp_all =
        let v=0.2f32 --TODO ESG, even for serial?
        let rfr=0.05f32
        let tt=real (as.p.termOS-as.t+2i32)
        in as with state_new.COG = putOption as.state_new.assetShareCF as.intermediate.gteeBen rfr tt v

    let dBen(as: state_cwp_all): state_cwp_all =
        as with state_new.dBen = f32.max as.intermediate.gteeBen as.state_new.assetShareCF

    let COG2(as: state_cwp_all): state_cwp_all = --TODO this is a simplificaion of the generated array function - should we alter the code gen to do this?
        let rfr=0.05f32
        let tt=real (as.p.termOS-as.t)
        in as with state_new.COG2 = map (putOption as.state_new.assetShareCF as.intermediate.gteeBen rfr tt)  (0.2f32 +. volAdjs )

    let COGDiff(as: state_cwp_all): state_cwp_all =
        as with state_new.COGDiff = as.state_new.COG2 -.- as.state__1.COG2

    let reserveCF(as: state_cwp_all): state_cwp_all =
        as with state_new.reserveCF = as.state_new.assetShareCF+as.state_new.COG  

    --Forcing: Futhark optimises away stuff it thinks you don't need, so there's a need to force everthing
    let forceTheIssue(as: state_cwp_all): state_cwp_all =
        as with forceTheIssue = 
            real(as.state_new.termO_S)+as.state_new.reserveCF+as.state_new.revBonusCF+as.state_new.survCF+
            as.state_new.assetShareCF+real(as.state_new.ageYrs+as.state_new.ageMths)+as.state_new.COG+sum(as.state_new.COG2)+as.state_new.dBen

    -- One period: pipeline transitions and storage
    let runOnePeriod(as: state_cwp_all): state_cwp_all=
        as |> COG3 |> termO_S |> ageMths |> ageYrs |> monthlyRates |> survCF |> cflow |> revBonusCF |> assetShareCF |>gteeBen |>
            COG |> dBen |> COG2 |> COGDiff |> reserveCF |> discFac |> discdCflow |> forceTheIssue

    -- Store results for next period
    let store(as: state_cwp_all): state_cwp_all = 
        let z = copy zerosArray --to avoid aliasing problems with the update in the next line
        let newVecsurvCF = update z as.t as.state_new.survCF
        in
        {
            p=as.p,
            state__2 = {dBen=as.state__1.dBen},
            state__1 = as.state_new, -- this is the only really important one!
            --"update" store-alls.  Can't use in-place!  This is the most efficient (seeming) way I can think of (alternatives: appending to end, use slicing).  OK, I used slicing as well.
            --note loop still works (see backdisc) so could go back to loop from iterate
            state__999={survCF = as.state__999.survCF +.+ newVecsurvCF, cflow = as.state__999.cflow[:as.t-1]++[as.results.cflow]++(zeros1 (numPeriods-as.t))},
            intermediate = as.intermediate,
            results= as.results,
            state_new = as.state_new,
            t=as.t+1,
            forceTheIssue=as.forceTheIssue*0.001f32, --carry forward the forcing, so all periods forced (hopefully)
            reserves=as.reserves, --overwritten separately
            basisNum=as.basisNum
        }

    -- time loop without reserving
    let runAllPeriods (n:i32) = iterate n (runOnePeriod>->store)

    -- finalisation (TODO currently only the identity)
    let runFinalise(as: state_cwp_all): state_cwp_all=
        as

    -- Cashflows and surv - TODO how can this be made user-specified?
    let runOneBasisAllCflows (as: state_cwp_all) (fromTime:i32 ) (bn:i32):[][]f32 = -- TODO generalise to return multiple values
        let as2=as with basisNum=bn
        let final_all_state = ((runAllPeriods (as.p.termOS-fromTime+1i32)) >-> runFinalise) as2
        let res=[final_all_state.state__999.cflow,final_all_state.state__999.survCF]
        in res

    -- one basis from one time
    let runOneBasisOneTime (as: state_cwp_all) (fromTime:i32 ) (bn:i32):f32 = -- TODO generalise to return multiple values

        let as2=as with basisNum=bn

        -- final state TODO final as in maturity
        let final_all_state = ((runAllPeriods (as.p.termOS-fromTime+1i32)) >-> runFinalise) as2

        let res=final_all_state.state_new.discdCflow --assuming only need reserves here, user needs to specify which columns are returned
        in res

    -- Rebased reserves (TODO needs generalising for arbitrary things calculated from "clones")
    -- This is based on appending, can also use the "zeros and add" method of survcf
    let calcRebasedReserves(as: state_cwp_all): state_cwp_all = 
        let theReserves = 
            if isRebaseTime[as.t-1] then
                (map (runOneBasisOneTime as (as.t-1)) (map (.2) (filter (.1) (zip doRebase (iota numBases))))) ++ (zeros1 numProxies) --FTB, for simplicity, assume all rebased bases come first
            else
                zeros1 numBases
        in as with reserves=as.reserves++[theReserves] --give up on in-place alteration, FTB; this will require a run-time check on the consistency of array sizes

    -- time loop with rebasing
    let runAllPeriodsWithRebasing (n:i32) = iterate n (runOnePeriod>->store>->calcRebasedReserves)

    -- define run function
    let runOnePol (pol:data_cwp) :[]f32 = 

        -- initialisation of state from data
        let init_state_cwp = init_cwp pol

        -- initial value of all-state
        let init_all_state:state_cwp_all = {
            p=pol,
            state__999 = {survCF=zerosArray,cflow=zerosArray},
            state__2 = {dBen=0f32},
            state__1=init_state_cwp,
            intermediate={gteeBen=0f32,qxMonthly=0f32,lapseRateMonthly=0f32},
            results={cflow=0f32},
            state_new=init_state_cwp, -- do not care what the values are so reuse initial values
            t=1i32,
            forceTheIssue=0f32,
            reserves = [],
            basisNum = 0i32
        }

        -- Phase1: run experience plus all rebased bases
        let final_all_state = ((runAllPeriodsWithRebasing pol.termOS) >-> runFinalise) init_all_state

        --run other proxied bases from t=1, returns survCF and all cashflows.  TODO why not return final all-state(s) here as well?
        let proxyStuff = map (runOneBasisAllCflows init_all_state 1i32) (map (.2) (filter ((.1)>->(!)) (zip doRebase (iota numBases))))

        --calculate proxy reserves
        let table_vs = map (map (\x->1/(1f32+x))) table_disc --convert rates to v, also need to transpose etc, not worth it now
        --create blank array to hold results
        let PVs = 
        --back discount cashflows for each basis
        let rsv1 = map3 backDisc table_vs PVs proxyStuff.something
        --adjust for survivorship
        --let proxyReserves = map 

        let res=[final_all_state.state_new.discdCflow,final_all_state.forceTheIssue]
        in res

    -- map run to data
    let allRes = map runOnePol data_cwp

    -- extract results

    -- reduce results (sum)

    in allRes