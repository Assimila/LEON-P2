## Useful functions ##

###############################################################################################
## 1. Defining function to extract value of EO data at sites

Extract_plantation_age_at_site <- function(site_longlat_coordinates,
                                           virtual_mosaic,
                                           buffer_crop_area,
                                           buffer_extract_data,
                                           baseline_year, 
                                           EO_Layer) {
  
  ## year of sampling of the biodiversity data
  site_sampling_date <- site_longlat_coordinates$Sample_start_earliest
  
  ## linear extent of sampling
  linear_extent <- site_longlat_coordinates$Max_linear_extent_metres
  
  ## get site coordinates
  site_long_lat <- site_longlat_coordinates %>% 
    vect(geom = c("Longitude", "Latitude"),
         crs="+proj=longlat")
  
  ## project point
  site_proj <- terra::project(
    site_long_lat,
    cea_crs_custom
  )
  
  ## buffer area around the site
  site_buffer <- buffer(site_long_lat, width=buffer_crop_area)
  
  ## crop virtual mosaic to extent
  vrtm_site <- terra::crop(virtual_mosaic, site_buffer)
  
  ## project buffered area
  vrtm_site_proj <- terra::project(
    vrtm_site,
    cea_crs_custom,
    method = "near", 
    res=30
  )
  
  ## add considered buffer size around site for the extraction
  site_longlat_coordinates$Buffer_extract_data <- buffer_extract_data
  
  ## Extract data from the EO-derived layer
  
  ## within a buffer --> derive AVERAGE age of the plantation at sampling
  if (!is.na(buffer_extract_data)) {
    ## extract the data from the EO-layer in the buffered zone
    buffer_age_proj <- extract(x = vrtm_site_proj,
                               y = buffer(site_proj, buffer_extract_data))
    
    ## in both datasets, 0 represent NAs/no plantation detected, thus replace by NA
    ind <- which(buffer_age_proj[, 2] == 0)
    buffer_age_proj[ind, 2] <- NA
    
    ## the data given in Danylo et al. is different from that given in the Descals layer. Descals et al. give the plantation year directly,
    ## while Danylo et al. report the difference from a baseline year (1980).
    
    if (EO_Layer == 'Danylo') {
      ## year of detection = recorded value + baseline year (1980)
      Detection_year_Danylo <- buffer_age_proj[, 2] + baseline_year
      
      ## calculate age at detection at sampling: sampling date is given, and we have the year of detection.
      
      ## In danylo et al. we get the year in which the oil palm plantation was first detected.
      # "At this point, the plantation is 2 to 3 years of age. The data values range from 0 to 37 where 0 is the No Data value
      # Values 1 to 3 are not present and a value of 4 corresponds to the year 1984, the first year oil palm was detected,
      # and each consecutive number represents the next year, i.e., 5 is 1985, while the maximum value of 37 corresponds
      # to 2017."
      
      ## age at sampling = sampling year - year of detection + 3 (when detected, the plantation is 2 to 3 years old)
      buffer_age_proj[, 2] <-
        as.numeric(format(site_sampling_date, '%Y')) - Detection_year_Danylo + 3
    }
    
    if (EO_Layer == 'Descals') {
      ## calculate plantation age: sampling date is given, and we have the year of planting
      ## age at sampling = sampling year - year of detection + 3 (when detected, the plantation is 2 to 3 years old)
      buffer_age_proj[, 2] <-
        as.numeric(format(site_sampling_date, '%Y')) - buffer_age_proj[, 2]
    }
    
    ## extracting mean, median, and median absolute deviation
    site_longlat_coordinates$buffer_age_proj_mean <-
      mean(buffer_age_proj[, 2], na.rm = TRUE)
    site_longlat_coordinates$buffer_age_proj_median <-
      median(buffer_age_proj[, 2], na.rm = TRUE)
    site_longlat_coordinates$buffer_age_proj_mad <-
      mad(buffer_age_proj[, 2], na.rm = TRUE)
    
    ## add layer name to relevant columns
    colnames(site_longlat_coordinates)[grepl('buffer_age_proj', colnames(site_longlat_coordinates))] <-
      paste0(EO_Layer, "_", colnames(site_longlat_coordinates)[grepl('buffer_age_proj', colnames(site_longlat_coordinates))])
    
    rm(buffer_age_proj)
    
  }
  
  ## within the max linear extent  --> derive AVERAGE age of the plantation at sampling in buffered area defined by maximum sampling linear extent at site
  if (!is.na(linear_extent)) {
    ## extract the data from the EO-layer in the buffered zone
    linear_extent_age_proj <- extract(x = vrtm_site_proj,
                                      y = buffer(site_proj, linear_extent))
    
    ## in both datasets, 0 represent NAs/no plantation detected, thus replace by NA
    ind <- which(linear_extent_age_proj[, 2] == 0)
    linear_extent_age_proj[ind, 2] <- NA
    
    ## the data given in Danylo et al. is different from that given in the Descals layer. Descals et al. give the plantation year directly,
    ## while Danylo et al. report the difference from a baseline year (1980).
    
    if (EO_Layer == 'Danylo') {
      ## year of detection = recorded value + baseline year (1980)
      Detection_year_Danylo <- linear_extent_age_proj[, 2] + baseline_year
      
      ## calculate age at detection at sampling: sampling date is given, and we have the year of detection.
      
      ## In danylo et al. we get the year in which the oil palm plantation was first detected.
      # "At this point, the plantation is 2 to 3 years of age. The data values range from 0 to 37 where 0 is the No Data value
      # Values 1 to 3 are not present and a value of 4 corresponds to the year 1984, the first year oil palm was detected,
      # and each consecutive number represents the next year, i.e., 5 is 1985, while the maximum value of 37 corresponds
      # to 2017."
      
      ## age at sampling = sampling year - year of detection + 3 (when detected, the plantation is 2 to 3 years old)
      linear_extent_age_proj[, 2] <-
        as.numeric(format(site_sampling_date, '%Y')) - Detection_year_Danylo + 3
    }
    
    if (EO_Layer == 'Descals') {
      ## calculate plantation age: sampling date is given, and we have the year of planting
      ## age at sampling = sampling year - year of detection + 3 (when detected, the plantation is 2 to 3 years old)
      linear_extent_age_proj[, 2] <-
        as.numeric(format(site_sampling_date, '%Y')) - linear_extent_age_proj[, 2]
    }
    
    ## extracting mean, median, and median absolute deviation
    site_longlat_coordinates$linear_extent_age_proj_mean <-
      mean(linear_extent_age_proj[, 2], na.rm = TRUE)
    site_longlat_coordinates$linear_extent_age_proj_median <-
      median(linear_extent_age_proj[, 2], na.rm = TRUE)
    site_longlat_coordinates$linear_extent_age_proj_mad <-
      mad(linear_extent_age_proj[, 2], na.rm = TRUE)
    
    ## add layer name to relevant columns
    colnames(site_longlat_coordinates)[grepl('linear_extent_age_proj', colnames(site_longlat_coordinates))] <-
      paste0(EO_Layer, "_", colnames(site_longlat_coordinates)[grepl('linear_extent_age_proj', colnames(site_longlat_coordinates))])
    
    rm(linear_extent_age_proj)
  }
  
  if(is.na(linear_extent)){
    site_longlat_coordinates$linear_extent_age_proj_mean <- NA
    site_longlat_coordinates$linear_extent_age_proj_median <-NA
    site_longlat_coordinates$linear_extent_age_proj_mad <- NA
    
    ## add layer name to relevant columns
    colnames(site_longlat_coordinates)[grepl('linear_extent_age_proj', colnames(site_longlat_coordinates))] <-
      paste0(EO_Layer, "_", colnames(site_longlat_coordinates)[grepl('linear_extent_age_proj', colnames(site_longlat_coordinates))])
  }
  
  ## without a buffer --> add age at EXACT location (in the 30m by 30m pixel)
  site_longlat_coordinates$age_longlat <-
    extract(x = vrtm_site, y = site_long_lat)[, 2]
  site_longlat_coordinates$age_cea <-
    extract(x = vrtm_site_proj, y = site_proj)[, 2]
  
  ## 0s represent NA values/ no plantation detected
  if (site_longlat_coordinates$age_longlat == 0) {
    site_longlat_coordinates$age_longlat <- NA
  }
  
  if (site_longlat_coordinates$age_cea == 0) {
    site_longlat_coordinates$age_cea <- NA
  }
  
  ## calculate plantation age
  if (EO_Layer == 'Danylo') {
    site_longlat_coordinates$age_longlat <-
      as.numeric(format(site_sampling_date, '%Y')) - (site_longlat_coordinates$age_longlat + baseline_year) + 3
    site_longlat_coordinates$age_cea <-
      as.numeric(format(site_sampling_date, '%Y')) - (site_longlat_coordinates$age_cea + baseline_year) + 3
    
  }
  
  if (EO_Layer == 'Descals') {
    site_longlat_coordinates$age_longlat <-  as.numeric(format(site_sampling_date,'%Y')) - site_longlat_coordinates$age_longlat 
    site_longlat_coordinates$age_cea <-  as.numeric(format(site_sampling_date,'%Y')) - site_longlat_coordinates$age_cea
    
  }
  
  colnames(site_longlat_coordinates)[grepl('age_longlat', colnames(site_longlat_coordinates))] <-
    paste0(EO_Layer, "_", colnames(site_longlat_coordinates)[grepl('age_longlat', colnames(site_longlat_coordinates))])
  colnames(site_longlat_coordinates)[grepl('age_cea', colnames(site_longlat_coordinates))] <-
    paste0(EO_Layer, "_", colnames(site_longlat_coordinates)[grepl('age_cea', colnames(site_longlat_coordinates))])
  
  return(site_longlat_coordinates)
  
}

###############################################################################################
## 2. Defining function to run Extract_plantation_age_at_site over sites (simple for-loop)

Loop_over_sites_Extract_age <- function(Sites_data,  
                                        virtual_mosaic,
                                        buffer_crop_area,
                                        buffer_extract_data,
                                        baseline_year, 
                                        EO_Layer){
  
  results_list <- list()
  
  for(i in 1:nrow(Sites_data)){
    
    results_list[[i]] <-
      Extract_plantation_age_at_site(
        site_longlat_coordinates = Sites_data[i, ],
        virtual_mosaic = virtual_mosaic,
        buffer_crop_area = buffer_crop_area,
        buffer_extract_data = buffer_extract_data,
        baseline_year = baseline_year,
        EO_Layer = EO_Layer
      )
    print(paste('site', i, 'over', nrow(Sites_data)))
  }
  
  results_frame <- data.table::rbindlist(results_list) %>% 
    as.data.frame()
  
  return(results_frame)
}


###############################################################################################
## 3. Defining functions to extract land cover from multiple layers around a PREDICTS site (given coordinates):
## required data/arguments are: EO LAYERS:
# ESA-CCI
# planting year for oil palm (Danylo or Descals)
# Intact forest landscape layer
# Austin et al industrial oil palm layer

## site coordinates and year of sampling (start); 
## buffer size around point


Extract_LC_classes_around_site <- function(site_longlat_coordinates, 
                                           ESA_CCI_layers, 
                                           EO_age_layer,
                                           EO_age_detection_layer,
                                           IFL_layer, 
                                           Austin_OP_layer, 
                                           buffer_crop_area, 
                                           buffer_extract_data, 
                                           Save_Plot){
  
  ## format start year of sampling
  Sampling_start_year <- lubridate::year(site_longlat_coordinates$Sample_start_earliest)
  
  ## check that the site was sampled between 1992 and 2015
  if(Sampling_start_year<1992|Sampling_start_year>2015){
    print('sampling year falls outside the temporal boundaries of ESA-CCI layers')
  }
  
  ## linear extent of sampling
  linear_extent <- site_longlat_coordinates$Max_linear_extent_metres
  
  ## get site coordinates
  site_long_lat <- site_longlat_coordinates %>% 
    vect(geom = c("Longitude", "Latitude"),
         crs="+proj=longlat")
  
  ## project point
  site_proj <- terra::project(
    site_long_lat,
    cea_crs_custom
  )
  
  ## buffer area around the site
  site_buffer <- buffer(site_long_lat, width=buffer_crop_area)
  
  #### Age layer
  
  ## crop the virtual mosaic to extent (for the age at detection layer)
  vrtm_site <- terra::crop(EO_age_detection_layer, site_buffer)
  
  ## project buffered area
  vrtm_site_proj <- terra::project(
    vrtm_site,
    cea_crs_custom,
    method = "near", 
    res=30
  )
  
  if(EO_age_layer=='Danylo'){
    vrtm_site_proj <- vrtm_site_proj + 1980 + 3
  }
  
  ## create a raster with planting year, excluding areas where OP was planted after biodiversity sampling
  planting_year_rast <- vrtm_site_proj
  planting_year_rast[planting_year_rast>Sampling_start_year] <- NA
  
  #### CCI layer
  
  ## find the appropriate CCI layer that match year of sampling and crop the layer to the specified buffer extent, and project the buffered area
  Match_years_layers <-
    function(year, spatial_layers) {
      return(spatial_layers[[names(spatial_layers) == year]])
    }
  
  CCI_layer <- Match_years_layers(year=Sampling_start_year, spatial_layers = ESA_CCI_layers)
  CCI_layer_site <- terra::crop(CCI_layer, site_buffer)
  
  CCI_layer_proj <- terra::project(
    CCI_layer_site,
    cea_crs_custom,
    method = "near", 
    res=30
  )
  
  #### IFL layer
  
  ## select the appropriate IFL layer (correct year)
  if(Sampling_start_year<=2000){
    IFL_layer <- IFL_layer[['2000']] 
  } else {
    IFL_layer <- IFL_layer[['2013']] 
  }
  
  ## crop and project the IFL data
  IFL_layer_crop <- terra::crop(IFL_layer, site_buffer)
  
  ## project buffered area
  IFL_layer_crop_proj <- terra::project(
    IFL_layer_crop,
    cea_crs_custom,
    method = "near", 
    res=30
  )
  
  #### industrial OP layer (Austin et al.)
  if(Sampling_start_year<=2002){
    Austin_layer <- Austin_OP_layer[['2000']] 
  }
  
  if(Sampling_start_year>2002 & Sampling_start_year<=2007){
    Austin_layer <-  Austin_OP_layer[['2005']] 
  }
  
  if(Sampling_start_year>2007){
    Austin_layer <- Austin_OP_layer[['2010']] 
  }
  
  Austin_layer <- terra::crop(Austin_layer, site_buffer)
  
  ## project buffered area
  Austin_proj <- terra::project(
    Austin_layer,
    cea_crs_custom,
    method = "near", 
    res=30
  )
  
  #### 
  
  ## add considered buffer size around site for the extraction to the results dataset
  site_longlat_coordinates$Buffer_extract_data <- buffer_extract_data
  
  #### Extract data from the EO-derived layer (here ESA-CCI) within the specified buffer ####
  
  if (is.na(buffer_extract_data)) {
    print('Buffer needs to be specified.')
  }
  
  if (!is.na(buffer_extract_data)) {
    
    #### extract the data from the EO-layer in the buffered zone
    
    ## CCI layer: we mask the CCI layers with the layer on oil palm plantation year
    
    # combine  CCI layer with the planting year layer; mask out areas where there are oil palm plantations
    planting_year_rast_resampled <- resample(planting_year_rast, CCI_layer_proj)
    planting_year_rast_resampled[planting_year_rast_resampled<1984] <- NA
    CCI_masked <- terra::mask(x=CCI_layer_proj, mask=planting_year_rast_resampled, inverse=TRUE)
    
    # # combine  CCI layer with the industrial oil palm layer; mask out areas where there are industrial oil palm plantations
    # ## to check
    # Austin_proj_resampled <- resample(Austin_proj, CCI_layer_proj)
    # CCI_masked <- terra::mask(x=CCI_masked, mask=Austin_proj_resampled, inverse=TRUE)
    
    ## resample rasters 
    IFL_layer_crop_proj_resampled <- resample(IFL_layer_crop_proj, CCI_layer_proj)
    Austin_proj_resampled <- resample(Austin_proj, CCI_layer_proj)
    
    CCI_values_extract <- extract(x = CCI_masked,
                                  y = buffer(site_proj, buffer_extract_data))
    colnames(CCI_values_extract)[2] <- "CCI_value"
    
    ## age layer
    planting_year_extract <- extract(x = planting_year_rast_resampled,
                                     y = buffer(site_proj, buffer_extract_data))
    
    age <- Sampling_start_year - planting_year_extract
    colnames(age)[2] <- "age_value"
    rm(planting_year_extract)
    
    ## IFL layer
    IFL_extract <- extract(x = IFL_layer_crop_proj_resampled,
                           y = buffer(site_proj, buffer_extract_data))
    colnames(IFL_extract)[2] <- "IFL_value"
    
    ## Industrial OP extract
    Ind_OP <- extract(x = Austin_proj_resampled,
                      y = buffer(site_proj, buffer_extract_data))
    colnames(Ind_OP)[2] <- "indOP_value"
    
    #### Join all extracted values 
    Values <- CCI_values_extract
    Values$age <- age$age_value
    Values$IFL <- IFL_extract$IFL_value
    Values$ind_OP_values <- Ind_OP$indOP_value
    
    #### PLOT ####
    if(Save_Plot){
      
      if(EO_age_layer=="Danylo"){
        Path <- paste0('../../Results/site_layers_plots/Danylo/', site_longlat_coordinates$SSBS, '.pdf')}
      if(EO_age_layer=="Descals"){
        Path <- paste0('../../Results/site_layers_plots/Descals/', site_longlat_coordinates$SSBS, '.pdf')}
      
      pdf(file=Path, width = 10, height = 10, pointsize = 12)
      
      par(mfrow=c(2,2))
      plot(vrtm_site_proj, main="Planting year"); points(site_proj, pch=19, cex=1.5)
      lines(buffer(site_proj, buffer_extract_data), col="red", lwd=2)
      plot(planting_year_rast, main="Planting year<=sampling date"); points(site_proj, pch=19, cex=1.5)
      lines(buffer(site_proj, buffer_extract_data), col="red", lwd=2)
      plot(CCI_layer_proj, main="ESA-CCI"); points(site_proj, pch=19, cex=1.5); 
      lines(buffer(site_proj, buffer_extract_data), col="red", lwd=2)
      plot(CCI_masked, main="ESA-CCI masked"); points(site_proj, pch=19, cex=1.5)
      lines(buffer(site_proj, buffer_extract_data), col="red", lwd=2)
      
      dev.off()
    }
    
    
    #### From the values extracted for the different layers, calculate, within the buffer area:
    ## % intact vegetation cover
    ## % industrial oil palm detected (Austin layer) cover
    ## % oil palm detected cover
    ## % cover of the different CCI categories
    ## in addition, for age: median age at sampling, + median absolute deviation
    
    ## % intact vegetation cover & % industrial OP as defined from Austin et al. layer
    Percent_IFL <- length(Values$IFL[!is.na(Values$IFL)])/length(Values$IFL)*100
    Percent_IndOP_Austin <- length(Values$ind_OP_values[!is.na(Values$ind_OP_values)])/length(Values$IFL)*100
    
    ## % oil palm detected cover, median age, median absolute deviation in age
    Percent_detected_OP <- length(Values$age[!is.na(Values$age)])/length(Values$age)*100
    Median_age <- median(Values$age, na.rm = TRUE)
    MAD_age <- mad(Values$age, na.rm = TRUE)
    
    ## add results to the dataframe
    site_longlat_coordinates <- 
      site_longlat_coordinates %>% 
      mutate(Percent_detected_OP=Percent_detected_OP, 
             Median_age=Median_age, 
             MAD_age=MAD_age, 
             Percent_IFL, 
             Percent_IndOP_Austin)
    
    ## % cover of the different CCI categories
    LU_categories <- unique(Values$CCI_value)[!is.na(unique(Values$CCI_value))]
    
    for(i in 1:length(LU_categories)){
      Val_fil <- Values %>% 
        filter(CCI_value==LU_categories[i])
      percent <- length(Val_fil$CCI_value)/length(Values$CCI_value)*100 %>% 
        as.data.frame() %>% 
        setNames(., paste0('LU_CCI_', as.character(LU_categories[i])))
      site_longlat_coordinates <- cbind(site_longlat_coordinates, percent)
    }
  }
  
  return(site_longlat_coordinates)
}




Loop_over_sites_Extract_LC <- function(Sites_data,  
                                       ESA_CCI_layers, 
                                       EO_age_layer,
                                       EO_age_detection_layer,
                                       IFL_layer, 
                                       Austin_OP_layer, 
                                       buffer_crop_area, 
                                       buffer_extract_data, 
                                       Save_Plot){
  
  results_list <- list()
  
  for(i in 1:nrow(Sites_data)){
    
    results_list[[i]] <- Extract_LC_classes_around_site(site_longlat_coordinates = Sites_data[i,],
                                                        ESA_CCI_layers = ESA_CCI_layers,
                                                        EO_age_detection_layer = EO_age_detection_layer, 
                                                        EO_age_layer = EO_age_layer,
                                                        IFL_layer = IFL_layer,
                                                        Austin_OP_layer = Austin_OP_layer, 
                                                        buffer_crop_area = buffer_crop_area,
                                                        buffer_extract_data = buffer_extract_data,
                                                        Save_Plot = Save_Plot)
    
    print(paste('site', i, 'over', nrow(Sites_data)))
  }
  
  results_frame <- data.table::rbindlist(results_list, fill = TRUE) %>% 
    as.data.frame()
  
  return(results_frame)
}

###############################################################################################
## 4. Defining functions for creating pairs of sites

## function to prepare the dataset of paired sites
CreatePairs <- function(study_name, input_data){
  
  # subset data for relevant study
  ss_data <- subset(input_data, SS==study_name)
  # get site information
  ss_data <- ss_data[, c("SSBS", "Predominant_land_use")]
  ss_data <- unique(ss_data)
  
  # get primary vegetation sites (comparison baseline)
  pv_sites <- ss_data$SSBS[ss_data$Predominant_land_use=="Primary vegetation"]
  # get all sites
  all_sites <- ss_data$SSBS
  
  # create pairwise combinations of these sites
  site_pairs <- expand.grid(pv_sites, all_sites)
  
  # remove pairs with same sites
  site_pairs <- site_pairs %>% 
    mutate(Var1=as.character(Var1), Var2=as.character(Var2)) %>%
    filter(Var1!=Var2)
  
  # remove duplicates (if A is paired with B, remove where B is paired with A)
  # sort rows alphabetically and take unique rows
  site_pairs <- t(apply(site_pairs, 1, sort))
  site_pairs <- as.data.frame(unique(site_pairs))
  colnames(site_pairs) <- c("SSBS_1", "SSBS_2")
  site_pairs$SS <- study_name
  
  # add land use information for each row
  lu_1 <- site_pairs %>% 
    dplyr::select(SSBS_1) %>% 
    dplyr::rename(SSBS=SSBS_1)
  lu_1 <- dplyr::left_join(lu_1, ss_data, by="SSBS") %>% 
    pull(Predominant_land_use)
  
  lu_2 <- site_pairs %>% 
    dplyr::select(SSBS_2) %>% 
    dplyr::rename(SSBS=SSBS_2)
  lu_2 <- dplyr::left_join(lu_2, ss_data, by="SSBS")%>% 
    pull(Predominant_land_use)
  
  site_pairs$lu_1 <- lu_1
  site_pairs$lu_2 <- lu_2
  
  # reorder the columns
  site_pairs <- site_pairs[, c('SS', 'SSBS_1', 'SSBS_2', 'lu_1', 'lu_2')]
  
  # reorder the columns, so that pv is always the reference LU (1)
  switch_ref_lu <- function(vect){
    if(vect[4]!=vect[5] & vect[5]=="Primary vegetation"){
      new_vect <- cbind(vect[1], vect[3], vect[2], vect[5], vect[4])
      colnames(new_vect) <- colnames(vect)
      return(new_vect)
    } else{
      return(vect)}
  }
  
  site_pairs_reorder <- as.data.frame(t(apply(site_pairs, 1, switch_ref_lu, simplify = TRUE)))
  colnames(site_pairs_reorder) <- colnames(site_pairs)
  
  ## add longitude and latitude for these pairs of sites
  LongLat_1 <- 
    site_pairs_reorder %>% 
    dplyr::select(SSBS_1) %>% 
    rename(SSBS=SSBS_1) %>%
    left_join(unique(input_data[, c('SSBS', 'Longitude', 'Latitude')])) %>% 
    rename(SSBS_1=SSBS, Longitude_1=Longitude, Latitude_1=Latitude)
  
  LongLat_2 <- 
    site_pairs_reorder %>% 
    dplyr::select(SSBS_2) %>% 
    rename(SSBS=SSBS_2) %>%
    left_join(unique(input_data[, c('SSBS', 'Longitude', 'Latitude')])) %>% 
    rename(SSBS_2=SSBS, Longitude_2=Longitude, Latitude_2=Latitude)
  
  site_pairs_reorder <- cbind(site_pairs_reorder, LongLat_1[, -1])
  site_pairs_reorder <- cbind(site_pairs_reorder, LongLat_2[, -1])
  rm(LongLat_1, LongLat_2)
  
  ## add geographical distances between pairs of sites
  site_pairs_reorder <- site_pairs_reorder %>% 
    dplyr::mutate(
      site_distance_meters = geosphere::distHaversine(
        cbind(Longitude_1, Latitude_1), cbind(Longitude_2, Latitude_2)))  
  
  # ## add sampling effort at sites
  # sampling_effort_1 <- 
  #   site_pairs_reorder %>% 
  #   dplyr::select(SSBS_1) %>% 
  #   rename(SSBS=SSBS_1) %>%
  #   left_join(unique(input_data[, c('SSBS', 'Sampling_effort', 'Rescaled_sampling_effort')])) %>% 
  #   rename(SSBS_1=SSBS, Sampling_effort_1=Sampling_effort, Rescaled_sampling_effort_1=Rescaled_sampling_effort)
  # 
  # sampling_effort_1 |> 
  #   group_by(SSBS_1) |> 
  # 
  # sampling_effort_2 <- 
  #   site_pairs_reorder %>% 
  #   dplyr::select(SSBS_2) %>% 
  #   rename(SSBS=SSBS_2) %>%
  #   left_join(unique(input_data[, c('SSBS', 'Sampling_effort', 'Rescaled_sampling_effort')])) %>% 
  #   rename(SSBS_1=SSBS, Sampling_effort_2=Sampling_effort, Rescaled_sampling_effort_2=Rescaled_sampling_effort)
  # 
  # site_pairs_reorder <- cbind(site_pairs_reorder, sampling_effort_1[, -1])
  # site_pairs_reorder <- cbind(site_pairs_reorder, sampling_effort_2[, -1])
  # rm(sampling_effort_1, sampling_effort_2)
  
  return(site_pairs_reorder)
  
}


###############################################################################################
## 5. Defining functions for calculating Bray Curtis dissimilarity

Calculate_Bray_Curtis_dissimilarity <-
  
  function(site_1, site_2, input_data) {
    
    ## subset data for the sites
    datasub <- subset(input_data, SSBS %in% c(site_1, site_2)) %>%
      dplyr::select(SSBS,
                    Taxon_name_entered,
                    Best_guess_binomial,
                    Effort_corrected_measurement)
    
    ## rescale abundance by total abundance at site (each sampled taxa represents a fraction of the total sampled abundance)
    datasub$relative_abundance <-
      datasub$Effort_corrected_measurement / sum(datasub$Effort_corrected_measurement)
    
    ## transpose data
    ab_data <-
      tidyr::pivot_wider(datasub[, c("SSBS", "Taxon_name_entered", "relative_abundance")],
                         names_from = Taxon_name_entered, values_from = relative_abundance) %>%
      tibble::column_to_rownames("SSBS")
    
    ## check the data: if all rows have no individuals (no sampled individuals at any site), return NA
    if(is.na(sum(rowSums(ab_data)))|sum(rowSums(ab_data))==0){
      bray_curtis_dist_vegan <- data.frame(SSBS_1=site_1, 
                                           SSBS_2=site_2,
                                           bray_curtis_distance_vegan=NA, 
                                           Calculation='all_0')
      return(bray_curtis_dist_vegan)
      
      ## check the data: if one of the sites has no individual
      
    } else if(any(rowSums(ab_data)==0)){
      
      bray_curtis_dist_vegan <- data.frame(SSBS_1=site_1, 
                                           SSBS_2=site_2,
                                           bray_curtis_distance_vegan=1, 
                                           Calculation='one_site_0') ## maximum dissimilarity applied here 
      
    } else { ## all sites have some sampled individuals
      
      ## comm_std <- decostand(community_matrix, method = "total")
      
      ## calculate Bray_Curtis dissimilarity: from the vegan package
      bray_curtis_dist_vegan <- vegan::vegdist(ab_data, method = "bray")
      #bray_curtis_dist_betapart <- betapart::bray.part(ab_data)
      
      bray_curtis_dist_vegan <-
        as.data.frame(as.table(as.matrix(bray_curtis_dist_vegan)))
      
      bray_curtis_dist_vegan$Var1 <- as.character(bray_curtis_dist_vegan$Var1)
      bray_curtis_dist_vegan$Var2 <- as.character(bray_curtis_dist_vegan$Var2)
      
      bray_curtis_dist_vegan <- bray_curtis_dist_vegan %>%
        filter(Var1 == site_1 & Var2 == site_2)
      colnames(bray_curtis_dist_vegan) <-
        c("SSBS_1", "SSBS_2", "bray_curtis_distance_vegan")
      bray_curtis_dist_vegan$Calculation <- "vegan"
      return(bray_curtis_dist_vegan)
      
    }
    
  }



###############################################################################################
## 6. Defining functions for plotting PREDICTS results: model effects

# Predict_effects <- function(new_data, 
#                             Model, 
#                             rescale, 
#                             LU_n, 
#                             backtransform=c('poisson', 'log+1', 'logit', 'asin_sqrt', 'sqrt'),
#                             A_logit) {
#   
#   preds <- sapply(X=1:100, FUN=function(i){
#     
#     coefs <- mvrnorm(n = 1, mu = fixef(object=Model), Sigma = vcov(object=Model))
#     mm <- model.matrix(terms(Model), new_data)
#     
#     # drop coefs that couldn't be estimated
#     #print(setdiff(colnames(mm), names(coefs)))
#     to_drop <- setdiff(colnames(mm), names(coefs))
#     if(length(to_drop)!=0){
#       mm <- as.data.frame(mm)
#       mm <- mm[, -which(colnames(mm) %in% to_drop)]
#       mm <- as.matrix(mm)
#     }
#     
#     # drop coefs for which we don't want predictions
#     to_drop2 <- setdiff(names(coefs), colnames(mm))
#     if(length(to_drop2)!=0){
#       coefs <- coefs[-which(names(coefs) %in% to_drop2)]
#     }
#     y <- mm %*% coefs
#     
#     # backtransforming
#     if(backtransform=='poisson'){    
#       y <- exp(y)
#     }
#     
#     if(backtransform=='log+1'){    
#       y <- exp(y)-1
#     }
#     
#     if(backtransform=='logit'){    
#       
#       inv_logit <- function(f, a){
#         a <- (1-2*a)
#         (a*(1+exp(f))+(exp(f)-1))/(2*a*(1+exp(f)))
#       }
#       y <- inv_logit(y, a=A_logit)
#     }
#     
#     if(backtransform=='asin_sqrt'){    
#       y <- (sin(y))^2
#     }
#     
#     
#     if(backtransform=='sqrt'){    
#       y <- y^2
#     }
#     
#     
#     
#     # rescaling
#     if(rescale){
#       
#       ## set reference land use at 100%, others at value/ref*100%
#       
#       if(LU_n!=nrow(new_data)){
#         # for loop to rescale all values
#         N <- (nrow(new_data)/LU_n-1)
#         for(i in 1:N){
#           seq <- seq + LU_n
#           y[seq] <- y[seq]/y[seq[1]]*100
#         }
#       }
#       
#       
#       if(LU_n==nrow(new_data)){
#         y <- y/y[1]*100
#       }
#       # seq <- 1:LU_n
#       # y[seq] <- y[seq]/y[seq[1]]*100
#       
#     }
#     
#     return(y)
#   })
#   
#   preds <- data.frame(Median=apply(X=preds, MARGIN=1, FUN=median),
#                       Upper=apply(X=preds, MARGIN=1, FUN=quantile, probs=0.975),
#                       Lower=apply(X=preds, MARGIN=1, FUN=quantile, probs=0.025))
#   preds <- cbind(preds, new_data)
#   return(preds)
#   
# }

Predict_effects_impr <- function(new_data, 
                            Model, 
                            rescale = FALSE, 
                            LU_n = NULL, 
                            backtransform = c('poisson', 'log+1', 'logit', 'asin_sqrt', 'sqrt'),
                            A_logit = NULL,
                            nsim = 100) {
  
  backtransform <- match.arg(backtransform)
  
  ## --- 1. Align factor levels with model ---
  mf <- model.frame(Model)
  
  for (v in names(mf)) {
    if (is.factor(mf[[v]]) && v %in% names(new_data)) {
      new_data[[v]] <- factor(new_data[[v]], levels = levels(mf[[v]]))
    }
  }
  
  ## --- 2. Build model matrix ---
  mm <- model.matrix(delete.response(terms(Model)), new_data)
  
  ## --- sanity check ---
  if (ncol(mm) != length(fixef(Model))) {
    stop("Model matrix and coefficients do not match. Check factor levels.")
  }
  
  ## --- 3. Draw nsim coefficient simulations ---
  coef_sims <- MASS::mvrnorm(
    n = nsim, 
    mu = fixef(Model), 
    Sigma = vcov(Model)
  )
  
  ## --- 4. Linear predictor, matrix multiplication ---
  preds <- mm %*% t(coef_sims)   # (n_obs × nsim)
  
  ## --- 5. Backtransforming ---
  inv_logit <- function(f, a){
    a <- (1 - 2 * a)
    (a * (1 + exp(f)) + (exp(f) - 1)) / (2 * a * (1 + exp(f)))
  }
  
  preds <- switch(backtransform,
                  poisson   = exp(preds),
                  `log+1`   = exp(preds) - 1,
                  logit     = inv_logit(preds, A_logit),
                  asin_sqrt = (sin(preds))^2,
                  sqrt      = preds^2
  )
  
  ## --- 6. Rescaling ---
  if (rescale) {
    
    if (is.null(LU_n)) stop("LU_n must be provided when rescale = TRUE")
    
    if (LU_n == nrow(new_data)) {
      preds <- sweep(preds, 2, preds[1, ], "/") * 100
    # } else {
    #   groups <- split(seq_len(nrow(preds)), 
    #                   ceiling(seq_len(nrow(preds)) / LU_n))
    #   
    #   for (g in groups) {
    #     preds[g, ] <- sweep(preds[g, ], 2, preds[g[1], ], "/") * 100
    #   }
    # }
    } else{
    ## need to define rescaling within land-use intensity groups -- 
      ## here, no need because we don't consider the interaction between land use and land use intensity; only the main effect of intensity.
    print('need to define rescaling within subgroups')
    }
    }
  
  ## --- 6. Preparing output data ---
  preds <- data.frame(Median=apply(X=preds, MARGIN=1, FUN=median),
                      Upper=apply(X=preds, MARGIN=1, FUN=quantile, probs=0.975),
                      Lower=apply(X=preds, MARGIN=1, FUN=quantile, probs=0.025)) %>%
    tibble::rownames_to_column(var = "id")
  
  new_data <- new_data %>%
    tibble::rownames_to_column(var = "id")
  
  preds <- new_data %>%
    left_join(preds, by = "id") 
  
  return(preds)  # matrix: rows = observations, cols = simulations
}


###############################################################################################
## 7. Defining functions for predicting BII around mills

Predict_BII <- function(UML_data, 
                        Buffer_mill,
                        WC_layer,
                        Year,
                        FI_layer,
                        Aggregate_Factor,
                        abundance_model=abundance_model_SV_treecover,
                        similarity_model=similarity_model_tree_cover, 
                        Path_raster_out){
  
  
  ## abundance predictions at the grid cell level -- set the reference level: for primary with 100% forest cover
  REF_Level_abundance <- 
    Predict_effects_impr(
      new_data = expand.grid(
        LandUse = c("Primary vegetation",
                    "Cropland"),
        LU_CCI_50 = 100),
      Model = abundance_model_SV_treecover,
      rescale = FALSE,
      backtransform = 'sqrt'
    )
  
  REF_Level_abundance <- REF_Level_abundance$Median[1]
  
  ## similarity predictions at the grid cell level -- set the reference level: for primary with 100% forest cover
  REF_Level_similarity <-
    Predict_effects_impr(
      new_data = expand.grid(
        contrast = c(
          "Primary vegetation-Primary vegetation",
          "Primary vegetation-Cropland"),
        log10_geodist = 0,
        LU_CCI_50 = 100
      ),
      Model = similarity_model_tree_cover,
      rescale = FALSE,
      backtransform = 'logit',
      A_logit = 0.001
    )
  REF_Level_similarity <- REF_Level_similarity$Median[1]
  
  ## initialise columns to store results
  UML_data$Median_BII <- NA
  UML_data$Sum_BII <- NA
  
  ## loop over mills and derive BII for each mill
  for (i in 1:nrow(UML_data)){
    
    gc()
    
    ## get mill coordinates and buffer
    coordinates_mills <-
      vect(matrix(c(
        as.numeric(UML_data$Longitude[i]),
        as.numeric(UML_data$Latitude[i])
      ), ncol = 2),
      crs = "+proj=longlat +datum=WGS84")
    
    coordinates_mills_buffer <- buffer(coordinates_mills, width=Buffer_mill)
    
    ## crop and mask the land cover layer and the forest integrity layer
    Extent_inter <-
      relate(WC_layer, coordinates_mills_buffer, "intersects")
    if (Extent_inter) {
      WC_cropped <- crop(WC_layer, coordinates_mills_buffer)
      WC_cropped_ag <-
        aggregate(WC_cropped, Aggregate_Factor, fun = 'modal')
      WC_cropped_masked <-
        mask(WC_cropped_ag, coordinates_mills_buffer)
    } else{
      next
    }
    
    FI_crop <- crop(FI_layer, WC_cropped_masked)
    FI_crop <- project(x = FI_crop, y = WC_cropped_masked)
    FI_mask <- mask(FI_crop, WC_cropped_masked)
    
    ## get the values of these layers, as dataframe for operations
    template <- as.data.frame(values(WC_cropped_masked))
    FI <- as.data.frame(values(FI_mask))
    template <- cbind(template, FI)
    colnames(template) <- c('WC_code', 'forest_integrity')
    
    ## encode the land uses -- here, there are pretty strong assumptions in terms of matching categories!
    template$LandUse <- NA
    template$LandUse[template$WC_code == 10 &
                       template$forest_integrity >= 7] <- 'Primary vegetation'
    template$LandUse[template$WC_code == 10 &
                       template$forest_integrity < 7 &
                       template$forest_integrity >= 5] <- 'Mature secondary vegetation'
    template$LandUse[template$WC_code == 10 &
                       template$forest_integrity < 5 &
                       template$forest_integrity >= 3] <- 'Intermediate secondary vegetation'
    template$LandUse[template$WC_code == 10 &
                       template$forest_integrity < 3 &
                       template$forest_integrity > 0] <- 'Young secondary vegetation'
    template$LandUse[template$WC_code == 20] <- 'Young secondary vegetation'
    template$LandUse[template$WC_code == 30] <- 'Young secondary vegetation'
    template$LandUse[template$WC_code == 60] <- 'Young secondary vegetation'
    template$LandUse[template$WC_code == 40] <- 'Cropland'
    template$LandUse[template$WC_code == 11] <- 'Oil palm plantation'
    
    template$LandUse[template$WC_code == 50] <- 'Urban'
    template$LandUse[template$WC_code == 70] <- 'Snow and ice'
    template$LandUse[template$WC_code == 80] <- 'Permanent water bodies'
    template$LandUse[template$WC_code == 90] <- 'Herbaceous wetland'
    template$LandUse[template$WC_code == 95] <- 'Mangroves'
    template$LandUse[template$WC_code == 100] <- 'Moss and lichen'
    
    template$contrast[!is.na(template$LandUse)] <- paste('Primary vegetation', template$LandUse[!is.na(template$LandUse)], sep='-' )
    
    ## add % tree cover as LU_CCI_50 ## WC code 10 = tree cover
    template$LU_CCI_50 <- nrow(template[which(template$WC_code==10),])/nrow(template)*100
    
    ## now predict for abundance at the grid cell level
    preds_abundance <-
      Predict_effects_impr(
        new_data = template,
        Model = abundance_model_SV_treecover,
        rescale = FALSE,
        backtransform = 'sqrt'
      )
    
    # template <- template %>%
    #   tibble::rownames_to_column(var = "id")
    # 
    # template <- template %>%
    #   left_join(preds_abundance[, c('Median', 'id')], by = "id") 
    # 
    # template$abundance_predictions_rescaled <-
    #   template$Median / REF_Level_abundance
    # 
    # template <- template %>% 
    #   dplyr::select(-Median)
    
    ## now predict for similarity at the grid cell level
    
    template$log10_geodist <- 0
    
    preds_similarity <-
      Predict_effects_impr(
        new_data = template,
        Model = similarity_model_tree_cover,
        rescale = FALSE,
        backtransform = 'logit',
        A_logit = 0.001
      )
    
    # template <- template %>%
    #   left_join(preds_similarity[, c('Median', 'id')], by = "id") 
    # 
    # template$similarity_predictions_rescaled <-
    #   template$Median / REF_Level_similarity
    
    BII <- (preds_abundance$Median/REF_Level_abundance) * (preds_similarity$Median/REF_Level_similarity)
    
    ## make a copy of out raster and allocate BII values
    Raster_outout <- WC_cropped_masked
    values(Raster_outout) <- BII
    
    UML_data$Median_BII[i] <- median(BII, na.rm=TRUE)
    UML_data$Sum_BII[i] <- sum(BII, na.rm=TRUE)
    
    print(paste('finished row', i, 'of', nrow(UML_data)))
    
    writeRaster(
      Raster_outout,
      paste0(Path_raster_out, Year, '/',
        UML_data$UML.ID[i],
        '.tif'
      ),

      overwrite=TRUE)
    
  }
  return(UML_data)
}


