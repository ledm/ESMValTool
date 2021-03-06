;;#############################################################################
;; REFORMAT SCRIPT FOR MODIS Level 3 OBSERVATIONAL DATA
;;#############################################################################
;;
;; Tier
;;    Tier 2: other freely-available dataset.
;;
;; Source
;;    http://modis-atmos.gsfc.nasa.gov/index.html
;;    The data set fetched is the,
;;         "MOD 08 - Gridded Atmospheric Product"
;;    i.e., monthly level 3 files from collection 6,
;;    these files are named,
;;         'MYD08_M3.AYYYYDDD.006*'
;;
;; Recommended acknowledgment for MODIS data (fetched from MODAPS)
;; Q: How do I acknowledge the use of MODAPS Data?
;;
;; A: The distribution of the MODAPS data sets are funded by NASA's
;; Earth-Sun System Division (ESSD). The data are not copyrighted;
;; however, in the event that you publish data or results using
;; these data, we request that you include the following acknowledgment:
;;
;; "The data used in this study were acquired as part of the NASA's
;; Earth-Sun System Division and archived and distributed by the
;; MODIS Adaptive Processing System (MODAPS)."
;;
;; We would appreciate receiving a copy of your publication, which
;; can be forwarded to MODAPSUSO@lists.nasa.gov.
;;
;; Last access
;;    20150504
;;
;; Download and processing instructions
;;    Download data follow instructions on the above link
;;    Edit the settings available in the
;;           'get_settings(...)'
;;    function below to be consistent with your system.
;;    Run with:
;;       ncl reformat_scripts/obs/reformat_obs_modis.ncl
;;
;; Caveats
;;    - Requires NCL v6.1.1 (due to the ':='-operator
;;    - Data is converted into separate monthly files, not yearly
;;    - clwvi and clivi data are in-cloud values whereas CMIP5 models
;;      provide grid-box averages --> multiply MODIS clwvi and clivi
;;      values with cloud fraction as a first guess
;;
;; Modification history
;;    20170116-A-laue_ax: using cirrus fraction to convert lwp and iwp
;;                        from in-cloud values to gridbox averages
;;                        (test)
;;    20160408-A-laue_ax: added processing of uncertainties
;;                        removed suffixes for variables names
;;    20151118-A-laue_ax: bugfix: added unit conversion
;;                        clivi, clwvi: g/m2 --> kg/m2
;;                        clt: frac --> %
;;    20150430-eval_ma: written.
;;
;;#############################################################################

load "./reformat_scripts/constants.ncl"

function get_settings(res [1]:logical)
; Settings for the various variables availabe in the WHOI data set
begin
    ;; Default settings
    res@year1 = 2002  ; start year
    res@year2 = 2014  ; end year
    res@modis_filename_prefix = "MYD08_M3.A"

    ;; Dimension names in the HDF file (lat/lon)
    res@lat_var = "YDim"
    res@lon_var = "XDim"
    res@lat_name = "YDim_mod08"
    res@lon_name = "XDim_mod08"

    ;; Variables to extract from HDF
    ;;       MODIS variable name                                 CMIP5 name
;     res@vars2copy = \
;         (/(/"Cloud_Fraction_Mean_Mean",                         "clt"        /), \
;           (/"Cloud_Water_Path_Liquid_Mean_Mean",                "clwvi"      /), \
;           (/"Cloud_Water_Path_Ice_Mean_Mean",                   "clivi"      /), \
;           (/"Cloud_Water_Path_Liquid_Mean_Uncertainty",         "lwpStderr"  /), \
;           (/"Cloud_Water_Path_Ice_Mean_Uncertainty",            "iwpStderr"  /), \
;           (/"AOD_550_Dark_Target_Deep_Blue_Combined_Mean_Mean", "od550aer"   /)/)
     res@vars2copy = \
         (/(/"Cloud_Water_Path_Liquid_Mean_Mean",                "clwvi"      /), \
           (/"Cloud_Water_Path_Ice_Mean_Mean",                   "clivi"      /), \
           (/"Cloud_Water_Path_Liquid_Mean_Uncertainty",         "lwpStderr"  /), \
           (/"Cloud_Water_Path_Ice_Mean_Uncertainty",            "iwpStderr"  /)/)

    ;; Input/ouput/working foldesr
    res@raw_data_folder = \
        getenv("ESMValTool_RAWOBSPATH") + "/Tier2/MODIS-L3-C6"
    res@processed_data_folder = \
        getenv("ESMValTool_OBSPATH") + "/Tier2/MODIS-L3-C6"

    return(res)
end

function get_time_from_filename(infile [1]:string)
; Compute the current time using the MODIS filename structure
local infile_str, yyyyddd, yyyymmdd, year, month,
    day, cal_res, time
begin

    yyyyddd  = toint(str_get_cols(infile, 10, 16))
    yyyymmdd = yyyyddd_to_yyyymmdd(yyyyddd)
    year     = toint(str_get_cols(tostring(yyyymmdd), 0, 3))
    month    = toint(str_get_cols(tostring(yyyymmdd), 4, 5))
    day      = toint(str_get_cols(tostring(yyyymmdd), 6, 7))
    cal_res = 0
    cal_res@calendar = "proleptic_gregorian"
    time = cd_inv_calendar(year, month, day, 0, 0, 0, TUNITS, cal_res)
    return time
end

function get_year_from_filename(infile [1]:string)
; Wrapper 'function to get_time_from_filename(...)' to
; retrieve current year
local time, times, year
begin
    time = get_time_from_filename(infile)
    times = cd_calendar(time, 0)
    year = toint(times(:, 0))
    return year
end

function get_month_from_filename(infile [1]:string)
; Wrapper 'function to get_time_from_filename(...)' to
; retrieve current month
local time, times, month
begin
    time = get_time_from_filename(infile)
    times = cd_calendar(time, 0)
    month = toint(times(:, 1))
    return month
end

procedure set_time_attributes(time [1]:double)
; Set CMIP5 time attributes
begin
    time@standard_name = "time"
    time@long_name = "time"
    time@axis = "T"
end

function append_history(infile [1]:file,
                        to_add [1]:string)
; Creates (or appends) a history string
local newline, f, datestamp, history
begin
    newline = str_get_nl()
    datestamp = systemfunc("date -u")

    ;; Check existing history attribute
    if (isatt(infile, "history")) then
        history = infile@history
    else
        history = ""
    end if

    ;; Create or append history
    if (strlen(history) .gt. 0) then
        history = datestamp + ": " + to_add + newline + history
    else
        history = datestamp + ": " + to_add
    end if
    return history
end

function get_output_filename(res [1]:logical,
                        var_name [1]:string,
                             mip [1]:string,
                            year [1]:integer,
                           month [1]:integer)
; Define the CMIP5 DRS output filename
local outfile_string, month_str
begin
    month_str = sprinti("%02i", month)
    outfile_string = \
        res@processed_data_folder + "/" + \
        "OBS_MODIS_sat_L3-C6_T2Ms_" + var_name + "_" + \
        tostring(year) + month_str + "-" + tostring(year) + month_str + ".nc"
    if (isfilepresent(outfile_string)) then
        system("rm -f " + outfile_string)
    end if
    return outfile_string
end

function get_modis_suffix(sufficies [*]: string,
                          index [1]:integer)
; Fetch the last part of the Modis variable. A wrapper
; is needed as the array might be both 1D or 2D
local ret_val, suff_sizes
begin
; A-laue_ax+
;    suff_sizes = dimsizes(dimsizes(sufficies))
;    if (suff_sizes .eq. 1) then
;        ret_val = sufficies(0)
;    else if(suff_sizes .eq. 2) then
;        ret_val = sufficies(index, 0)
;    else
;        print("fatal: in get_modis_suffix (reformat_obs_modis.ncl) invalid array size")
;    end if
;    end if
    ret_val = sufficies(index)
; A-laue_ax-
    return ret_val
end

function get_cmip_suffix(sufficies [*]: string,
                         index [1]:integer)
; Fetch the last part of the Modis variable. A wrapper
; is needed as the array might be both 1D or 2D
local ret_val, suff_sizes
begin
    suff_sizes = dimsizes(dimsizes(sufficies))
    if (suff_sizes .eq. 1) then
        ret_val = sufficies(1)
    else if(suff_sizes .eq. 2) then
        ret_val = sufficies(index, 1)
    else
        print("fatal: in get_cmip_suffix (reformat_obs_modis.ncl) invalid array size")
    end if
    end if
    if (strlen(ret_val) .gt. 0) then
        ret_val = "-" + ret_val
    end if
    return ret_val
end

load "./interface_scripts/messaging.ncl"
load "./reformat_scripts/obs/reformat_obs_func.ncl"

begin
    res = True
    res = get_settings(res)

    diag_script = "reformat_obs_modis.ncl"

    ;; Create output dir
    if (.not. isfilepresent_esmval(res@processed_data_folder)) then
        system("mkdir -p " + res@processed_data_folder)
    end if

    ;; Loop over all indicated years
    do yy = res@year1, res@year2
        timestamp = systemfunc("date")
        print(timestamp + "  --  year: " + yy\
                        + " (in range " + res@year1\
                        + " to " + res@year2 + ")")
        files := systemfunc("ls -1 " + res@raw_data_folder + "/"\
                                     + res@modis_filename_prefix\
                                     + yy + "*")

        ;; Loop over all files in indicated year
        ;; (MODIS is provided in monthly files)
        do file_idx = 0, dimsizes(files) - 1
            inpath_str = files(file_idx)
            infile_str = systemfunc("basename " + inpath_str)
            fin = addfile(inpath_str, "r")

            ;; Current date is encoded in filename
            time = get_time_from_filename(infile_str)
            year = get_year_from_filename(infile_str)
            month = get_month_from_filename(infile_str)
            set_time_attributes(time)

            ;; Loop over variables to fetch from input file
; A-laue_ax+
            no_vars = dimsizes(res@vars2copy)
;            no_vars_root = dimsizes(res@vars2copy_root)
;            ;; The "root" part of the MODIS variable filename
;            do var_idx_root = 0, no_vars_root(0) - 1
;                vars_root = res@vars2copy_root
;                vars = res@vars2copy_var
;                no_vars = dimsizes(vars)
;                ;; The "suffix" (last) part of the MODIS variable filename
;                do var_idx = 0, no_vars(0) - 1
;                    invar_str = vars_root(var_idx_root, 0) + "_" + get_modis_suffix(vars(:,0), var_idx)
;                    outvar_str = vars_root(var_idx_root, 1)
;                    outvar_str = outvar_str + get_cmip_suffix(vars(:,1), var_idx)
            vars = res@vars2copy
            do var_idx = 0, no_vars(0) - 1
                    invar_str = vars(var_idx, 0)
                    outvar_str = vars(var_idx, 1)
                    print(invar_str + "--->" + outvar_str)
; A-laue_ax-

                    ;; Read file, scale data, and copy along meta data
                    invar = fin->$invar_str$
                    invar_fv = invar@_FillValue
                    invar_coords = invar
                    invar := tofloat(invar)
                    invar := where(invar .eq. tofloat(invar_fv), default_fillvalue("float"), invar)
; A-laue_ax+
                    ; calculate clwvi by adding lwp + iwp
                    if (outvar_str.eq."clwvi") then
                        if (invar_str.ne."Cloud_Water_Path_Liquid_Mean_Mean") then
                            print("Critical error: cannot calculate clwvi. Abort.")
                        end if
                        ; read cirrus fraction
                        cfin = fin->Cirrus_Fraction_SWIR_FMean
;                        cifin = fin->Cirrus_Fraction_Infrared_FMean
                        cif = tofloat(cfin * cfin@scale_factor + cfin@add_offset)
                        ; estimate liquid fraction
                        lif = 1.0 - cif

                        ; read ice water path
                        tmpvar = fin->Cloud_Water_Path_Ice_Mean_Mean
                        tmpvar_fv = tmpvar@_FillValue
                        tmpvar := tofloat(tmpvar)
                        tmpvar := where(tmpvar .eq. tofloat(tmpvar_fv), default_fillvalue("float"), tmpvar)
;    system ("rm debug.nc")
;    debugfile = addfile("debug.nc","c")
;    debugfile->lif = lif
;    debugfile->cif = cif
;    debugfile->lwp_before = tmpvar

                        ; convert lwp in-cloud value to grid-box average
                        tmpvar = tmpvar * lif

;    debugfile->lwp_after = tmpvar
;    debugfile->clivi_before = invar

                        ; convert iwp in-cloud value to grid-box average
                        invar = invar * cif

;    debugfile->clivi_after = invar
;    exit

                        ; now calculate clwvi = lwp + iwp
                        invar = invar + tmpvar
                        delete(tmpvar)
                        delete(lif)
                        delete(cif)
                        delete(cfin)
                    end if

                    ; lwp and iwp are in-cloud values
                    ; --> convert lwp/iwp to grid-box averages by multiplying with
                    ; average cloud fraction (not optimum but best we can do at the moment)
                    if (any(outvar_str.eq.(/"clwvi", "clivi", "iwpStderr", "lwpStderr"/))) then
                        ; read cirrus fraction (0-1)
                        cfin = fin->Cirrus_Fraction_SWIR_FMean
;                        cf = fin->Cirrus_Fraction_Infrared_FMean
                        cf = tofloat(cfin * cfin@scale_factor + cfin@add_offset)
                        if (any(outvar_str.eq.(/"clwvi", "lwpStderr"/))) then
                            cf = 1.0 - cf
                        end if
                        ; now calculate "grid-box average" lwp/iwp
;    system ("rm debug.nc")
;    debugfile = addfile("debug.nc","c")
;    debugfile->cf = cf
;    debugfile->invar_before = invar
                        invar = invar * cf
;    debugfile->invar_after = invar
;    exit
                        delete(cf)
                        delete(cfin)
                        ; convert units from g/m2 to kg/m2
                        invar = 0.001 * invar
                    end if

                    ; convert to correct units
                    if (outvar_str.eq."clt") then
                         invar = 100.0 * invar  ; frac --> %
                    end if
; A-laue_ax-
                    invar@_FillValue = default_fillvalue("float")
                    copy_VarCoords(invar_coords, invar)
;                    if (isatt(invar_coords, "scale_factor")) then
;                        invar = invar * tofloat(invar_coords@scale_factor)
;                    end if
;                    if (isatt(invar_coords, "add_offset")) then
;                        invar = invar + tofloat(invar_coords@add_offset)
;                    end if

                    ;; Create output variable
                    lat = fin->$res@lat_var$
                    lon = fin->$res@lon_var$
                    outvar = new((/1, dimsizes(lat), dimsizes(lon)/), float)

                    ;; Set variable attributes
;                    if (get_modis_suffix(vars(:,0), var_idx) .eq. "Mean") then
                        outvar(0, :, :) = var_attrib(invar, outvar_str)
;                    end if

                    ;; Set reformatted time dimension
                    outvar!0 = "time"
                    outvar&time = time

                    ;; Set reformatted latitude dimension
                    outvar!1 = "lat"
                    outvar&lat = lat
                    if (isMonotonic(outvar&lat) .eq. 0) then
                        error_msg("fatal",\
                                  diag_script,\
                                  "",\
                                  "non-monotonic latitude coordinate")
                    end if
                    if (isMonotonic(outvar&lat) .eq. -1) then
                        outvar = outvar(:, ::-1, :)
                    end if
                    clat := lat_attrib(outvar&lat)
                    outvar&lat := clat

                    ;; Set reformatted longitude dimension
                    outvar!2 = "lon"
                    outvar&lon = lon
                    if (isMonotonic(outvar&lon) .eq. 0) then
                        error_msg("fatal",\
                                  diag_script,\
                                  "",\
                                  "non-monotonic longitude coordinate")
                    end if
                    if (any(outvar&lon .lt. 0.)) then
                        outvar = lonFlip(outvar)
                    end if
                    clon := lon_attrib(outvar&lon)
                    outvar&lon := clon

                    ;; Define output file with unlimited time dimension
                    outfile = get_output_filename(res,\
                                                  outvar_str,\
                                                  "Amon",\
                                                  year,\
                                                  month)
                    fout = addfile(outfile, "c")
                    filedimdef(fout, "time", -1, True)

                    ;; Copy along global attributes
; A-laue_ax+
                    if (isdefined("global_attnames")) then
                        delete(global_attnames)
                    end if
; A-laue_ax-
                    global_attnames = getvaratts(fin)
                    do i = 0, dimsizes(global_attnames) - 1
                        old_attr_prefix = "original-attr_"
                        attr = old_attr_prefix + global_attnames(i)
                        ;; 'history' attribute is handled below
                        if (ismissing(str_match(global_attnames(i), "Metadata_"))) then
                            fout@$attr$ =  fin@$global_attnames(i)$
                        end if
                    end do

                    ;; Copy along variable attributes
                    variable_attnames = getvaratts(invar_coords)
                    do i = 0, dimsizes(variable_attnames) - 1
                        old_attr_prefix = "original-attr_"
                        attr = old_attr_prefix + variable_attnames(i)
                        ;; 'history' attribute is handled below
                        if (.not. (variable_attnames(i) .eq. "history")) then
                            outvar@$attr$ = invar_coords@$variable_attnames(i)$
                        end if
                    end do

                    ;; Set global attributes sprecific for this script
                    fout@history = append_history(fin, "data reformatted to be used in ESMValTool")
                    fout@host    = systemfunc("hostname")
                    fout@user    = systemfunc("whoami")
                    fout@field   = "T2Ms"
                    fout@tier    = 2
                    fout@title   = "MOD 08 - Gridded Atmospheric Product reformatted for ESMValTool"
                    fout->$outvar_str$ = outvar

                    delete(invar)
                    delete(invar_coords)
                    delete(outvar)
                    delete(variable_attnames)
;                end do
            end do
        end do
    end do
end
