--note: the library functions have been updated

type real=f32
type int=i32

--utilities
let udne(x:*[]f32) (i:i32) (v:f32):(*[]f32)=
    if length x==0 then x else update x i v

--maths
let int(x:f32):i32=i32.f32(x)

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

let maxi(x:i32) (y:i32):i32=i32.max x y 

let maxr(x:f32) (y:f32):f32=f32.max x y 

--constants

let zeros1(s:i32):[]f32=

	replicate s 0.0f32

let zeros2 (s1:i32) (s2:i32) :[][]f32=

	replicate s1 (replicate s2 0.0f32)

let zeros3 (s1:i32) (s2:i32) (s3:i32) :[][][]f32=

	replicate s1 (replicate s2 (replicate s3 0.0f32))

let zerosi1(s:i32):[]i32=

	replicate s 0


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
let backDisc [n] (cflow:[n]f32) (v:[]f32):[n]f32=

    let discd=
    if n==0 then 
        [] 
    else
        let PVs:*[]f32= copy (zeros1 n)
        let PVs'=update PVs (n-1) cflow[n-1]
        let (discd'',_)= loop (discd':*[]f32,t':i32) = (PVs',(n-1)) while t'>=1i32 do (discd' with [t'-1] = discd'[t']*v[t']+cflow[t'-1],(t'-1))
        in discd''
    in discd

type gender=int
let male:i32=0
let female:i32=1

type smoker=int
let smoker:i32=0
let nonSmoker:i32=1

let firstProjectionPeriod:i32=(-12)
let lastProjectionPeriod:i32=(600)

--for single life is it a genuine single life or a surviving spouse
type mainLife=int
let mainLife:i32=0
let survivor:i32=1

--arbitrary health status
type health=int
let health1:i32=0
let health2:i32=1
let health3:i32=2
let health4:i32=3
let health5:i32=4

--pension band
type pens=int
let pensionLow:i32=0
let pensionHigh:i32=1

--occupation
type occ=int
let occ1:i32=0
let occ2:i32=0
let occ3:i32=0
let occ4:i32=0
let occ5:i32=0

--sector
type sector=int
let public:i32=0
let private:i32=1

--post code rankings
type poCode=int
let poCode1:i32=0
let poCode2:i32=1
let poCode3:i32=2
let poCode4:i32=3
let poCode5:i32=4

--pension scheme
type scheme=int
let sch1:i32=0
let sch2:i32=1
let sch3:i32=2
let sch4:i32=3
let sch5:i32=4

type inPayment=int
let paying:i32=0
let deferred:i32=1

type schInfo=int
let dataDateYears:i32=0
let dataDateMonths:i32=1

type basis=int
let Experience:i32=0
let RsvUK:i32=1
let RsvS2:i32=2
let RsvIFRS:i32=3
--record for holding general NR results for one item for all bases
type NR_results={
    RsvUK:[]f32,
    RsvS2:[]f32
}
let nrEmpty:NR_results={RsvUK=[],RsvS2=[]}
let doRebase=[false,false,false,true]
let rebaseTimes:[]i32=[1200]

type data_ia={
    sex:[2]gender,
    ageYears:[2]int,--as at the data date
    ageMonths:[2]int,
    stateOfHealth:[2]health,
    pensLevel:pens,
    occ:[2]occ,
    sector:[2]sector,
    poCode:poCode,
    scheme:scheme,
    inPayment:inPayment,
    dateLeaveYear:int,
    dateLeaveMonth:int,
    NRD:int,
    GMP:[5]real,--notional slices; will not implement full rules as that would be a hopeless task!  As at data date, say
    totalPension:real,
    gteePeriod:int,
    spousePropn:real,
    overlap:int,
    mainLife:int,
    smoker:[2]int,
    termPhase0:int
}

type derived_ia={
    termOS:int,
    termToDataDate:int
}

let dataFromArrays_ia [nr] (dataInt:[nr][]i32) (dataReal:[nr][]f32):[]data_ia=
    map2 (\x y :data_ia->{
        sex=[x[0],x[1]],
        ageYears=[x[2],x[3]],
        ageMonths=[x[4],x[5]],
        stateOfHealth=[x[6],x[7]],
        pensLevel=x[8],
        occ=[x[9],x[10]],
        sector=[x[11],x[12]],
        poCode=x[13],
        scheme=x[14],
        inPayment=x[15],
        dateLeaveYear=x[16],
        dateLeaveMonth=x[17],
        NRD=x[18],
        GMP=[y[0],y[1],y[2],y[3],y[4]],
        totalPension=y[5],
        gteePeriod=x[19],
        spousePropn=y[6],
        overlap=x[20],
        mainLife=x[21],
        smoker=[x[22],x[23]],
        termPhase0=x[24]
        }
        ) dataInt dataReal

type state_ia={
    survCF_back:[2]real,
    ageYears_back:[2]int,
    ageMonths_back:[2]int,
    calYear_back:int,
    calMonth_back:int,
    survCF:[2]real,
    ageYears:[2]int,
    ageMonths:[2]int,
    calYear:int,
    calMonth:int,
    rsvsUK:real,
    rsvsS2:real,
    rsvsIFRS:real,
    cflow:real
}

type state_ia_inter={
    qx:[2]real,
    survCF_LS:real
}

type state_ia_all={
    p:data_ia,
    der:derived_ia,
    state__1:state_ia,
    intermediate:state_ia_inter,
    state_new:state_ia,
    t:i32,
    basisNum:i32
}

let main  [np] [nb]  (fileDataInt_ia:[np][]i32) (fileDataReal_ia:[np][]f32) 
    (tbl_mort_sch:[nb][][][][]f32) (tbl_mort_smk:[][]f32) (tbl_mort_ml:[][]f32) (tbl_mort_hlt:[][]f32) (tbl_mort_hi:[][]f32) (tbl_mort_occ:[][]f32)
    (tbl_mort_pub:[][]f32) (tbl_mort_po:[][]f32) (tbl_sch_info:[][]f32)
    (tbl_vs:[][nb]f32)
    :[][]f32=

    unsafe

--common code
let maxage=115--hack to avoid falling off end of tables
let valYear=2018
let valMonth=12
let numPeriods=lastProjectionPeriod-firstProjectionPeriod+1

let rbtrue=replicate (length rebaseTimes) true
let rbts:*[]bool = replicate 1500 false --note large length to avoid going off the end
let isRebaseTime:*[]bool=scatter rbts rebaseTimes rbtrue

--put user functions here so can see tables

let setDerived_ia(d:data_ia):derived_ia=
    let termOS=maxage*12-(maxi (d.ageYears[0]*12+d.ageMonths[0]) (d.ageYears[1]*12+d.ageMonths[1]))
    let termToDataDate=12*valYear+valMonth-12*int(tbl_sch_info[d.scheme,dataDateYears])-int(tbl_sch_info[d.scheme,dataDateMonths])
    in{termOS=termOS,termToDataDate=termToDataDate}--there will be multiple data-dates.  Should pols start phase1 at the d-d or at firstprojectionperiod??  That is, is it desirable for all policies to be running the same t?

let fileData_ia=dataFromArrays_ia fileDataInt_ia fileDataReal_ia
let derived_ia=map setDerived_ia fileData_ia

let numRebased = length(filter (id) doRebase)
let numNonRebased = length(filter (!) doRebase)
let rebasedBases=map (numNonRebased+) (iota numRebased)
let zerosArray=zeros1 numPeriods

let runOnePeriod_phase0 (as:state_ia_all) :state_ia_all=
    --these calcs make no sense for an annuity but at least serve to illustrate a phase0
    let qx(as:state_ia_all):state_ia_all=
        let qx_arr1(i1:i32):f32=
            let age=as.state_new.ageYears_back[i1]
            let qx_ann=tbl_mort_sch[as.basisNum,as.p.scheme,as.p.sex[i1],age,as.state_new.calYear_back-2016i32]*
                tbl_mort_hi[age,as.p.pensLevel]*tbl_mort_hlt[age,as.p.stateOfHealth[i1]]*
                tbl_mort_ml[age,as.p.mainLife]*tbl_mort_occ[age,as.p.occ[i1]]*tbl_mort_po[age,as.p.poCode]*
                tbl_mort_pub[age,as.p.sector[i1]]*tbl_mort_smk[age,as.p.smoker[i1]]
            in 1-(1-qx_ann)**(1.0/12.0)
        let qx_res=map qx_arr1 (iota 2)
        in as with intermediate.qx=qx_res

    let calYear_back_calMonth_back(as:state_ia_all):state_ia_all=
        let cm0=as.state__1.calMonth_back-1
        let cy=if cm0>0 then as.state__1.calYear_back else as.state__1.calYear_back-1
        let cm=if cm0>0 then cm0 else 12
        let (y_res,m_res)=(cy,cm)
        in as with state_new.calYear_back=y_res with state_new.calMonth_back=m_res

    let ageMonths_back(as:state_ia_all):state_ia_all=
        let ageMonths_back_arr1(i1:i32):i32=
            let am0=as.state__1.ageMonths_back[i1]-1
            in if am0>=0 then am0 else 11
        let ageMonths_back_res=map ageMonths_back_arr1 (iota 2)
        in as with state_new.ageMonths_back=ageMonths_back_res

    let ageYears_back(as:state_ia_all):state_ia_all=
        let ageYears_back_arr1(i1:i32):i32=
            if as.state_new.ageMonths_back[i1]!=11 then as.state__1.ageYears_back[i1] else as.state__1.ageYears_back[i1]-1
        let ageYears_back_res=map ageYears_back_arr1 (iota 2)
        in as with state_new.ageYears_back=ageYears_back_res

    let survCF_back(as:state_ia_all):state_ia_all=
        let survCF_back_arr1(i1:i32):f32=
            as.state__1.survCF_back[i1]/(1-as.intermediate.qx[i1])
        let survCF_back_res=map survCF_back_arr1 (iota 2)
        in as with state_new.survCF_back=survCF_back_res

    let store_phase0(as:state_ia_all):state_ia_all= --no need for any assignment to store-alls on phase0
        as with state__1=as.state_new with t=as.t-1

    in as |> ageMonths_back |> ageYears_back |> calYear_back_calMonth_back |> qx |> survCF_back |> store_phase0

let runNPeriods_phase0 (n:i32) (as:state_ia_all):state_ia_all= --again, simple for phase0
    loop as':state_ia_all =as for i<n do (runOnePeriod_phase0 as')

let init_phase0 (d:data_ia) (der:derived_ia):state_ia=
    let survCF_back_arr1(i1:i32):f32=1
    let survCF_back=map survCF_back_arr1 (iota 2)
    let ageYears_back_arr1(i1:i32):i32=d.ageYears[i1]
    let ageYears_back=map ageYears_back_arr1 (iota 2)
    let ageMonths_back_arr1(i1:i32):i32=d.ageMonths[i1]
    let ageMonths_back=map ageMonths_back_arr1 (iota 2)
    let calYear_back=valYear
    let calMonth_back=valMonth
    in
    {
        survCF_back=survCF_back,
        ageYears_back=ageYears_back,
        ageMonths_back=ageMonths_back,
        calYear_back=calYear_back,
        calMonth_back=calMonth_back,
        survCF=zeros1 2,
        ageYears=zerosi1 2,
        ageMonths=zerosi1 2,
        calYear=0,
        calMonth=0,
        rsvsUK=0,
        rsvsS2=0,
        rsvsIFRS=0,
        cflow=0
    }

let init_phase0_all(d:data_ia) (der:derived_ia):state_ia_all=
    let init_state=init_phase0 d der in
    {
        p=d,
        der=der,
        state__1=init_state,
        intermediate={qx=(zeros1 2),survCF_LS=0},
        state_new=init_state,
        t=0,
        basisNum=0
    }

--params: inputs (named) from NR and from R, state and store-alls to calculate (all of them, whatever basis - but some might be empty)
let runOnePeriod_ia_phase1 (nr_survCF:NR_results) (nr_unadjdRsvs:NR_results) (as:state_ia_all) (cflow':*[]f32) (survCF':*[]f32) (rsvsUK':*[]f32) (rsvsS2':*[]f32) (rsvsIFRS':*[]f32) :
    (state_ia_all,*[]f32,*[]f32,*[]f32,*[]f32,*[]f32)=

    let qx(as:state_ia_all):state_ia_all=
        let qx_arr1(i1:i32):f32=
            let age=as.state_new.ageYears[i1]
            let qx_ann=tbl_mort_sch[as.basisNum,as.p.scheme,as.p.sex[i1],age,as.state_new.calYear-2016i32]*
                tbl_mort_hi[as.p.pensLevel,age]*tbl_mort_hlt[as.p.stateOfHealth[i1],age]*
                tbl_mort_ml[as.p.mainLife,age]*tbl_mort_occ[as.p.occ[i1],age]*tbl_mort_po[as.p.poCode,age]*
                tbl_mort_pub[as.p.sector[i1],age]*tbl_mort_smk[as.p.smoker[i1],age]
            in 1-(1-qx_ann)**(1.0/12.0)
        let qx_res=map qx_arr1 (iota 2)
        in as with intermediate.qx=qx_res

    let calYear_calMonth(as:state_ia_all):state_ia_all=
        let cm0=as.state__1.calMonth+1
        let cy=if cm0<=12 then as.state__1.calYear else as.state__1.calYear+1
        let cm=if cm0<=12 then cm0 else 1
        let (y_res,m_res)=(cy,cm)
        in as with state_new.calYear=y_res with state_new.calMonth=m_res

    let ageMonths(as:state_ia_all):state_ia_all=
        let ageMonths_arr1(i1:i32):i32=
            let am0=as.state__1.ageMonths[i1]+1
            in if am0<=11 then am0 else 0
        let ageMonths_res=map ageMonths_arr1 (iota 2)
        in as with state_new.ageMonths=ageMonths_res

    let ageYears(as:state_ia_all):state_ia_all=
        let ageYears_arr1(i1:i32):i32=
            if as.state_new.ageMonths[i1]!=0 then as.state__1.ageYears[i1] else as.state__1.ageYears[i1]+1
        let ageYears_res=map ageYears_arr1 (iota 2)
        in as with state_new.ageYears=ageYears_res

    let survCF(as:state_ia_all):state_ia_all=
        let survCF_arr1(i1:i32):f32=
            as.state__1.survCF[i1]*(1-as.intermediate.qx[i1])
        let survCF_res=map survCF_arr1 (iota 2)
        in as with state_new.survCF=survCF_res

    let survCF_LS(as:state_ia_all):state_ia_all=
        let survCF_LS=as.state_new.survCF[0]+as.state_new.survCF[1]-as.state_new.survCF[0]*as.state_new.survCF[1]
        in as with intermediate.survCF_LS=survCF_LS

    let cflow(as:state_ia_all):state_ia_all=
        --dummy
        let cflow_res=as.p.totalPension*as.intermediate.survCF_LS
        in as with state_new.cflow=cflow_res

    let rsvsUK(as:state_ia_all):state_ia_all= 
        let rsvsUK_res=
        if nr_unadjdRsvs.RsvUK==[] then
            0
        else
            nr_unadjdRsvs.RsvUK[as.t-firstProjectionPeriod]/nr_survCF.RsvUK[as.t-firstProjectionPeriod]*as.intermediate.survCF_LS
        in as with state_new.rsvsUK=rsvsUK_res

    let rsvsS2(as:state_ia_all):state_ia_all=
        let rsvsS2_res=
        if nr_unadjdRsvs.RsvS2==[] then
            0
        else
            nr_unadjdRsvs.RsvS2[as.t-firstProjectionPeriod]/nr_survCF.RsvS2[as.t-firstProjectionPeriod]*as.intermediate.survCF_LS
        in as with state_new.rsvsS2=rsvsS2_res

    let store_phase1(as:state_ia_all) (cflow:*[]f32) (survCF:*[]f32) (rsvsUK:*[]f32) (rsvsS2:*[]f32) (rsvsIFRS:*[]f32):
        (state_ia_all,*[]f32,*[]f32,*[]f32,*[]f32,*[]f32)=
        ((as with state__1=as.state_new with t=as.t+1),(udne cflow (as.t-firstProjectionPeriod) as.state_new.cflow),(udne survCF (as.t-firstProjectionPeriod) as.intermediate.survCF_LS),
        (udne rsvsUK (as.t-firstProjectionPeriod) as.state_new.rsvsUK),(udne rsvsS2 (as.t-firstProjectionPeriod) as.state_new.rsvsS2),(udne rsvsIFRS (as.t-firstProjectionPeriod) as.state_new.rsvsIFRS))

    let asPreStore= as |> ageMonths |> ageYears |> calYear_calMonth |> qx |> survCF |> survCF_LS |> cflow |> rsvsUK |> rsvsS2
    in store_phase1 asPreStore cflow'  survCF' rsvsUK' rsvsS2' rsvsIFRS'

--the following is used only in bases - the equivalent for experience (which also has rebasing) runNPeriodsWithRebasing_ia.  Hence the nr_ will be empties as will the rsvs_
let runNPeriods_ia_phase1 (n:i32) (nr_survCF:NR_results) (nr_unadjdRsvs:NR_results) (as:state_ia_all) (cflow:*[]f32) (survCF:*[]f32) (rsvsUK:*[]f32) (rsvsS2:*[]f32) (rsvsIFRS:*[]f32) :
    (state_ia_all,*[]f32,*[]f32,*[]f32,*[]f32,*[]f32)=
    loop (as':state_ia_all,cflow':*[]f32,survCF':*[]f32,rsvsUK':*[]f32,rsvsS2':*[]f32,rsvsIFRS':*[]f32) =
        (as,cflow,survCF,rsvsUK,rsvsS2,rsvsIFRS) for i<n do 
            runOnePeriod_ia_phase1 nr_survCF nr_unadjdRsvs as' cflow' survCF' rsvsUK' rsvsS2' rsvsIFRS' 

let init_phase1 (d:data_ia) (der:derived_ia) (s:state_ia):state_ia=
    let survCF_arr1(i1:i32):f32=s.survCF_back[i1]
    let survCF=map survCF_arr1 (iota 2)
    let ageYears_arr1(i1:i32):i32=s.ageYears_back[i1]
    let ageYears=map ageYears_arr1 (iota 2)
    let ageMonths_arr1(i1:i32):i32=s.ageMonths[i1]
    let ageMonths=map ageMonths_arr1 (iota 2)
    let calYear=s.calYear_back
    let calMonth=s.calMonth_back
    in s 
        with survCF=survCF 
        with ageYears=ageYears 
        with ageMonths=ageMonths
        with calYear=calYear
        with calMonth=calMonth

let init_phase1_all(d:data_ia) (der:derived_ia)(as:state_ia_all):state_ia_all=
	let state_bf= init_phase1 d der as.state_new
	in as with state_new=state_bf with state__1=state_bf with t=firstProjectionPeriod

let runOneBasisFromOneTime_ia (as: state_ia_all) (fromTime:i32 )  (cflow:*[]f32) (survCF:*[]f32) (bn:i32):(*[]f32,*[]f32,[]f32)= --will need to be careful to add the * where necessary
	let as2=as with basisNum=bn
	let (_,cflow',survCF',_,_,_) = runNPeriods_ia_phase1 (as.der.termOS-fromTime+1i32) nrEmpty nrEmpty as2 cflow survCF [] [] []--this is used only to run bases so we can keep the NR results empty.  Similarly the rebased reserves slots as they are yet to be calculated.
    let unadjdRsvs=backDisc cflow' tbl_vs[:,bn] --this line derives from a whole-array calc for NR, not needed for rebased and will be discarded in calcRebasedResults
    in (cflow',survCF',unadjdRsvs)

let calcRebasedResults_ia (as:state_ia_all,cflow:*[]f32,survCF:*[]f32,rsvsUK:*[]f32,rsvsS2:*[]f32,rsvsIFRS:*[]f32): --we know this only ever takes the o/p of something that returns a tuple so it can take a tuple
    (state_ia_all,*[]f32,*[]f32,*[]f32,*[]f32,*[]f32)=
        let (cflow',survCF',_)=runOneBasisFromOneTime_ia as (as.t) cflow survCF rebasedBases[0] --for simplicity, do one rebased reserve at a time as the results are being placed in specific calcs, in the general case there'd be several calls here (each call will eat cflow etc.).  
        let rsvsIFRS'':*[]f32=udne rsvsIFRS (as.t-firstProjectionPeriod) (sumprod  cflow'[(as.t-firstProjectionPeriod):] tbl_vs[(as.t-firstProjectionPeriod):,RsvIFRS])--this would stem from a calc, note it updates a single value.  It is not obvious how to cater for table indexing when the table does not start as 0 (just take the expression in [] and deduct the minimum)  Or, convert the table name to a function that adjusts the index.
        --in general case would have other rebased calls here
        in (as,cflow',survCF',rsvsUK,rsvsS2,rsvsIFRS'')--cflow and survCF have been overwritten from the rebase time onwards, but so what

let runNPeriodsWithRebasing_ia (n:i32) (nr_survCF:NR_results) (nr_unadjdRsvs:NR_results) (as:state_ia_all) (cflow:*[]f32) (survCF:*[]f32) (rsvsUK:*[]f32) (rsvsS2:*[]f32) (rsvsIFRS:*[]f32):
    (state_ia_all,*[]f32,*[]f32,*[]f32,*[]f32,*[]f32)=   --this is only run in Experience so can explicitly return experience outputs only
        loop (as':state_ia_all,cflow':*[]f32,survCF':*[]f32,rsvsUK':*[]f32,rsvsS2':*[]f32,rsvsIFRS':*[]f32) =
            (as,cflow,survCF,rsvsUK,rsvsS2,rsvsIFRS) for i<n do 
                if !isRebaseTime[as.t+1] then--needed so that if,for example, t=12 then rebase is run from start 13
                    runOnePeriod_ia_phase1 nr_survCF nr_unadjdRsvs as' cflow' survCF' rsvsUK' rsvsS2' rsvsIFRS' 
                else
                    calcRebasedResults_ia (runOnePeriod_ia_phase1 nr_survCF nr_unadjdRsvs as' cflow' survCF' rsvsUK' rsvsS2' rsvsIFRS')

let runOnePol_ia (pol:data_ia) (der:derived_ia):[][]f32 =
    --phase 0 (this never has store-alls so is simpler than the others)
    let init_as_prePhase0=init_phase0_all pol der
    let init_as_postPhase0=runNPeriods_phase0 (1-firstProjectionPeriod) init_as_prePhase0

    --init for phase1(experience+non-rebased alike)
	let init_as_prePhase1=init_phase1_all pol der init_as_postPhase0

    --run the non-rebased
    --convention: all's are prefixed "all_", suffixed with the basis and are created from outside the run so that if empty values are passed in they will be ignored; all arrays are separate variables.  Note no need to create ones that are created by whole array operations within the calls (unadjRsvs in this case).
    let all_cflow_NR1:*[]f32=copy zerosArray
    let all_survCF_NR1:*[]f32=copy zerosArray
    --this is used in rebased and so needs to return the union of NR and R results - but can ignore the ones we don't need; in this case that's cflow
	let (_,nr_survCF1,nr_unadjdrsvs1)= runOneBasisFromOneTime_ia init_as_prePhase1 firstProjectionPeriod all_cflow_NR1 all_survCF_NR1 1--usual failure of functional stuff in presence of in-place means we cannot use map so run NRs separately and package the results as a record of arrays.  Anyway, the store-alls need to be separate for each basis.  I had forgotten that.
    let all_cflow_NR2:*[]f32=copy zerosArray
    let all_survCF_NR2:*[]f32=copy zerosArray
	let (_,nr_survCF2,nr_unadjdrsvs2)= runOneBasisFromOneTime_ia init_as_prePhase1 firstProjectionPeriod all_cflow_NR2 all_survCF_NR2 2

    --assemble NR results by item
    --we might still wish to put these in a 2d array instead, if arrayed calcs prove absolutely essential
    let nr_survCF:NR_results={RsvUK=nr_survCF1,RsvS2=nr_survCF2}
    let nr_unadjdRsvs:NR_results={RsvUK=nr_unadjdrsvs1,RsvS2=nr_unadjdrsvs2}

    --store-alls specifically for the experience run
    let all_cflow_EXP:*[]f32=copy zerosArray
    let all_rsvsUK_EXP:*[]f32=copy zerosArray
    let all_rsvsS2_EXP:*[]f32=copy zerosArray
    let all_rsvsIFRS_EXP:*[]f32=copy zerosArray
    --experience (phase1, incl. rebasing).  Returns (in this example) cashflow and three sets of reserves over time.  Can return an explict tuple as it's just one basis, not a map as in NR.  Also return state for phase2 onwards...
    --pass in results of NR first, then state then store-alls for this phase (note the empties, which are not needed on this phase)
    let (asPostPhase1,all_cflow_EXP',_,all_rsvsUK_EXP',all_rsvsS2_EXP',all_rsvsIFRS_EXP') = 
        runNPeriodsWithRebasing_ia (der.termOS-firstProjectionPeriod+1) nr_survCF nr_unadjdRsvs
        init_as_prePhase1 all_cflow_EXP [] all_rsvsUK_EXP all_rsvsS2_EXP all_rsvsIFRS_EXP

    -- phase2, should it exist

    --get output of phase1
    in [all_cflow_EXP',all_rsvsUK_EXP',all_rsvsS2_EXP',all_rsvsIFRS_EXP']

--to avoid memory problems, we will do a batching loop; the following constant should perhaps be user set
--this cannot be done in dependent mode of course
--of course, maybe Futhark is clever enough to do the batching itself but would not wish to take that risk presently
let batchSize:i32=50000
let numBatches=np//batchSize--need to make this more sophisticated, also we need to add each batch into the running total, so need to pad (somehow) the final one
let sumOfBatches=
    loop sumOfBatches':[][][]f32=(zeros3 batchSize 4 numPeriods) for i<numBatches do
        let lo=i*batchSize
        let hi=(i+1)*batchSize
        let batchRes=map2 runOnePol_ia fileData_ia[lo:hi] derived_ia[lo:hi]
        in sumOfBatches' +...+ batchRes

in reduce (+..+) (zeros2 4 numPeriods) sumOfBatches