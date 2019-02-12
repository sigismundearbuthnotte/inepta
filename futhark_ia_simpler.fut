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
let undefined:f32=3.14159e20

let zeros1(s:i32):[]f32=

	replicate s 0.0f32

let zeros2 (s1:i32) (s2:i32) :[][]f32=

	replicate s1 (replicate s2 0.0f32)

let zeros3 (s1:i32) (s2:i32) (s3:i32) :[][][]f32=

	replicate s1 (replicate s2 (replicate s3 0.0f32))

let zerosi1(s:i32):[]i32=

	replicate s 0

let undef3 (s1:i32) (s2:i32) (s3:i32) :[][][]f32=

	replicate s1 (replicate s2 (replicate s3 undefined))


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

type gender=int
let male:i32=0
let female:i32=1

type smoker=int
let smoker:i32=0
let nonSmoker:i32=1

let firstProjectionPeriod:i32=1
let lastProjectionPeriod:i32=600

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

let doRebase=[false,false,false,true]
let rebaseTimes:[]i32=[1200]--not daring to rebase at present!

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
    survCF:[2]real,
    ageYears:[2]int,
    ageMonths:[2]int,
    calYear:int,
    calMonth:int,
    rsvsUK:real,
    rsvsS2:real,
    rsvsIFRS:real,
    cflow:real,
    survCF_LS:real
}

type state_ia_all={
    p:data_ia,
    der:derived_ia,
    state__1:state_ia
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

let i_cflow:i32=0
let i_survcf1:i32=1
let i_survcf2:i32=2
let i_unadjrsvs1:i32=3
let i_unadjrsvs2:i32=4
let i_rsvsUK:i32=5
let i_rsvsS2:i32=6
let i_rsvsIFRS:i32=7

let runOnePeriod_ia_phase1 (t:i32) (basisNum:i32) (sa:[][][]f32) (as:state_ia_all) (p:i32) :state_ia_all=

    let (calYear,calMonth)=
        let cm0=as.state__1.calMonth+1
        let cy=if cm0<=12 then as.state__1.calYear else as.state__1.calYear+1
        let cm=if cm0<=12 then cm0 else 1
    in (cy,cm)

    let ageMonths_arr1(i1:i32):i32=
        let am0=as.state__1.ageMonths[i1]+1
    in if am0<=11 then am0 else 0
    let ageMonths=map ageMonths_arr1 (iota 2)

    let ageYears_arr1(i1:i32):i32=
        if ageMonths[i1]!=0 then as.state__1.ageYears[i1] else as.state__1.ageYears[i1]+1
    let ageYears=map ageYears_arr1 (iota 2)

    let qx_arr1(i1:i32):f32=
        let age=ageYears[i1]
        let qx_ann=tbl_mort_sch[basisNum,as.p.scheme,as.p.sex[i1],age,calYear-2016i32]*
            tbl_mort_hi[age,as.p.pensLevel]*tbl_mort_hlt[age,as.p.stateOfHealth[i1]]*
            tbl_mort_ml[age,as.p.mainLife]*tbl_mort_occ[age,as.p.occ[i1]]*tbl_mort_po[age,as.p.poCode]*
            tbl_mort_pub[age,as.p.sector[i1]]*tbl_mort_smk[age,as.p.smoker[i1]]
    in 1-(1-qx_ann)**(1.0/12.0)
    let qx=map qx_arr1 (iota 2)

    let survCF_arr1(i1:i32):f32=
        as.state__1.survCF[i1]*(1-qx[i1])
    let survCF=map survCF_arr1 (iota 2)

    let survCF_LS=survCF[0]+survCF[1]-survCF[0]*survCF[1]

    let cflow=as.p.totalPension*survCF_LS

    let rsvsUK=
    if basisNum!=0 then
        0
    else
        sa[i_unadjrsvs1,t-firstProjectionPeriod,p]/sa[i_survcf1,t-firstProjectionPeriod,p]*survCF_LS

    let rsvsS2=
    if basisNum!=0 then
        0
    else
        sa[i_unadjrsvs2,t-firstProjectionPeriod,p]/sa[i_survcf2,t-firstProjectionPeriod,p]*survCF_LS

    let rsvsIFRS=sa[i_rsvsIFRS,t-firstProjectionPeriod,p]

    let state__1:state_ia=
    {
        survCF=survCF,
        ageYears=ageYears,
        ageMonths=ageMonths,
        calYear=calYear,
        calMonth=calMonth,
        rsvsUK=rsvsUK,
        rsvsS2=rsvsS2,
        rsvsIFRS=rsvsIFRS,
        cflow=cflow,
        survCF_LS=survCF_LS
    }
in as with state__1=state__1

let init_phase1 (d:data_ia) (der:derived_ia):state_ia=
    let survCF_arr1(i1:i32):f32=1
    let survCF=map survCF_arr1 (iota 2)
    let ageYears_arr1(i1:i32):i32=d.ageYears[i1]
    let ageYears=map ageYears_arr1 (iota 2)
    let ageMonths_arr1(i1:i32):i32=d.ageMonths[i1]
    let ageMonths=map ageMonths_arr1 (iota 2)
    let calYear=valYear
    let calMonth=valMonth
    in
    {
        survCF=survCF,
        ageYears=ageYears,
        ageMonths=ageMonths,
        calYear=calYear,
        calMonth=calMonth,
        rsvsUK=0,
        rsvsS2=0,
        rsvsIFRS=0,
        cflow=0,
        survCF_LS=0
    }

let init_phase1_all(d:data_ia) (der:derived_ia):state_ia_all=
    let init_state=init_phase1 d der in
    {
        p=d,
        der=der,
        state__1=init_state
    }

let runBatch [np] (fileDataBatch:[np]data_ia) (derivedBatch:[np]derived_ia):[][][]f32 = 
    let storeAlls:*[][][]f32=copy (undef3 8 numPeriods np) 
	let init_as=map2 init_phase1_all fileDataBatch derivedBatch
    let term=derivedBatch[0].termOS

    let (_,storeAlls1)=
    loop (as':[np]state_ia_all,storeAlls':*[][][]f32)=
        (init_as,storeAlls) for i<term do 
            let t=i+1
            let as''=map2 (runOnePeriod_ia_phase1 t 1 storeAlls') as' (iota np)
            let storeAlls''= (storeAlls' with [i_cflow,t]=(map (.state__1.cflow) as'') with [i_survcf1,t]=(map (.state__1.survCF_LS) as''))
            in (as'',storeAlls'')
    
    let storeAlls2=
    loop (storeAlls':*[][][]f32)=(storeAlls1 with [i_unadjrsvs1,term-1]=copy storeAlls1[i_cflow,term-1]) for i<term do 
            let t=term-i in
            storeAlls' with [i_unadjrsvs1,t-1]=(tbl_vs[t,1]*.storeAlls'[i_unadjrsvs1,t])+.+storeAlls'[i_cflow,t-1]

    let (_,storeAlls3)=
    loop (as':[np]state_ia_all,storeAlls':*[][][]f32)=
        (init_as,storeAlls2) for i<term do 
            let t=i+1
            let as''=map2 (runOnePeriod_ia_phase1 t 2 storeAlls') as' (iota np)
            let storeAlls''= (storeAlls' with [i_cflow,t]=(map (.state__1.cflow) as'') with [i_survcf2,t]=(map (.state__1.survCF_LS) as''))
            in (as'',storeAlls'')
    
    let storeAlls4=
    loop (storeAlls':*[][][]f32)=(storeAlls3 with [i_unadjrsvs2,term-1]=copy storeAlls3[i_cflow,term-1]) for i<term do 
            let t=term-i in
            storeAlls' with [i_unadjrsvs2,t-1]=(tbl_vs[t,2]*.storeAlls'[i_unadjrsvs2,t])+.+storeAlls'[i_cflow,t-1]

    let (_,storeAlls5)=
    loop (as':[np]state_ia_all,storeAlls':*[][][]f32)=
        (init_as,storeAlls4) for i<term do 
            let t=i+1
            let as''=map2 (runOnePeriod_ia_phase1 t 0 storeAlls') as' (iota np)
            let storeAlls''= (storeAlls' with [i_cflow,t]=(map (.state__1.cflow) as'') with [i_rsvsUK,t]=(map (.state__1.rsvsUK) as'') with [i_unadjrsvs2,t]=(map (.state__1.rsvsS2) as''))  
            in (as'',storeAlls'')
in [storeAlls5[i_cflow,:,:],storeAlls5[i_rsvsUK,:,:],storeAlls5[i_rsvsS2,:,:]]

let batchSize:i32=1--50000
let numBatches=np//batchSize
let sumOfBatches=
    loop sumOfBatches':[][][]f32=(zeros3 3 numPeriods batchSize) for i<numBatches do
        let lo=i*batchSize
        let hi=(i+1)*batchSize
        let batchRes=runBatch fileData_ia[lo:hi] derived_ia[lo:hi]
        in sumOfBatches' +...+ batchRes

in 
map (map (reduce  (+) 0 )) sumOfBatches