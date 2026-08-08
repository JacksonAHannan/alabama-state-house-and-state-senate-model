Alabama 2024 General Election Precinct Boundaries and Election Results

## RDH Date Retrieval
04/21/25

## Sources
Precinct-level election data from Alabama Secretary of State (https://www.sos.alabama.gov/alabama-votes/voter/election-data). Votes reported at the county-level (or Judicial Division in Jefferson County) are allocated to precincts based off of each precincts share of election-day votes for each candidate. For Jefferson County, documentation was found on the county website noting the Judicial Division corresponding to each precinct.

All counties not listed below use the [Alabama 2022 Precinct Boundary and Election Results file](https://redistrictingdatahub.org/dataset/alabama-2022-general-election-precinct-level-results-and-boundaries/) as their source, which itself draws the [Alabama 2020 Precinct Boundary and Election Results file](https://redistrictingdatahub.org/dataset/vest-2020-alabama-precinct-and-election-results/). 

Baldwin: Shapefile sourced from the county's website
Bullock: Image of 2024 voting precincts from Bullock County Democrat Executive Committee
Butler: Map retrieved from county commission office
Calhoun: Precincts aligned to commission districts using commission district map and voter file for confirmation
Clarke: Precincts modified based on precinct map provided by Board of Registers and voter file, as parts of the map were obscured
Coffee: Map retrieved from county commission website
Covington: Map retrieved from contact with County Administrator
Dallas: Unable to retrieve map through county contact, Valley Grande Baptist Precinct edited based on voter file
Henry: Map retrieved from contact with Board of Registrars
Houston: Shapefile retrieved online
Jefferson: Map retrieved from county contact and online precinct change documentation
Lee: Map retrieved from Lee County Commission minutes
Limestone: Map retrieved from county website lacks detail of particular precinct boundaries and unable to obtain more detailed map, voter file also utilized.
Madison: Shapefile downloaded from county website
Mobile: Shapefile downloaded from county website
Montgomery: Shapefile downloaded from county GIS website
Morgan: Shapefile downloaded from county GIS website
Pike: Shapefile received via contact with County Board of Registrars
Russell: Received shapefile from Public Records request
Shelby: Map and shapefile available via county website.
St. Clair: Shapefile downloaded from county GIS website
Tuscaloosa: Shapefile downloaded from county website
Washington: Received 2018-2020 map from County, no more recent map was available. Precincts created using this map and the voter file.

## Notes on Field Names:
Columns reporting votes generally follow the pattern: 
One example is:
G16PREDCLI
The first character is G for a general election, P for a primary, S for a special, and R for a runoff.
Characters 2 and 3 are the year of the election.*
Characters 4-6 represent the office type (see list below).
Character 7 represents the party of the candidate.
Characters 8-10 are the first three letters of the candidate's last name.

Election Type Codes Used:
G - General

Office Codes Used:
A## - Amendment
AJ# - Associate Justice of the Supreme Court
CFJ - Chief Justice of the Supreme Court
CR# - Court of Criminal Appeals Judge
CV# - Court of Civil Appeals Judge
PRE - President of the United States
PSC - President, Public Service Commission
CON## - US House of Representatives

Party Codes Used:
D - Democratic
I - Independent
O - Other / Write-In
R - Republican

## Fields:
***al_2024_gen_all_prec***
Field Name Description
UNIQUE_ID  Unique ID for each precinct                                                        
COUNTYFP   County FIP identifier                                                              
County     County Name                                                                        
Precinct   Precinct Name
G24A01NO   PROPOSED STATEWIDE AMENDMENT NUMBER ONE (1)-:-No-:-NON                             
G24A01YES  PROPOSED STATEWIDE AMENDMENT NUMBER ONE (1)-:-Yes-:-NON                            
G24AJ1OWRI ASSOCIATE JUSTICE OF THE SUPREME COURT, PLACE 1-:-Write-In-:-NON                   
G24AJ1RMCC ASSOCIATE JUSTICE OF THE SUPREME COURT, PLACE 1-:-Chris McCool-:-REP               
G24AJ2OWRI ASSOCIATE JUSTICE OF THE SUPREME COURT, PLACE 2-:-Write-In-:-NON                   
G24AJ2RBRY ASSOCIATE JUSTICE OF THE SUPREME COURT, PLACE 2-:-Tommy Bryan-:-REP                
G24AJ3OWRI ASSOCIATE JUSTICE OF THE SUPREME COURT, PLACE 3-:-Write-In-:-NON                   
G24AJ3RSEL ASSOCIATE JUSTICE OF THE SUPREME COURT, PLACE 3-:-Will Sellers-:-REP               
G24AJ4OWRI ASSOCIATE JUSTICE OF THE SUPREME COURT, PLACE 4-:-Write-In-:-NON                   
G24AJ4RMIT ASSOCIATE JUSTICE OF THE SUPREME COURT, PLACE 4-:-Jay Mitchell-:-REP               
G24CFJDGRI CHIEF JUSTICE OF THE SUPREME COURT-:-Greg Griffin-:-DEM                            
G24CFJOWRI CHIEF JUSTICE OF THE SUPREME COURT-:-Write-In-:-NON                                
G24CFJRSTE CHIEF JUSTICE OF THE SUPREME COURT-:-Sarah Stewart-:-REP                           
G24CR1OWRI COURT OF CRIMINAL APPEALS JUDGE, PLACE 1-:-Write-In-:-NON                          
G24CR1RMIN COURT OF CRIMINAL APPEALS JUDGE, PLACE 1-:-Richard Minor-:-REP                     
G24CR2OWRI COURT OF CRIMINAL APPEALS JUDGE, PLACE 2-:-Write-In-:-NON                          
G24CR2RAND COURT OF CRIMINAL APPEALS JUDGE, PLACE 2-:-Rich Anderson-:-REP                     
G24CR3OWRI COURT OF CRIMINAL APPEALS JUDGE, PLACE 3-:-Write-In-:-NON                          
G24CR3RCOL COURT OF CRIMINAL APPEALS JUDGE, PLACE 3-:-Bill Cole-:-REP                         
G24CV1OWRI COURT OF CIVIL APPEALS JUDGE, PLACE 1-:-Write-In-:-NON                             
G24CV1REDW COURT OF CIVIL APPEALS JUDGE, PLACE 1-:-Christy Edwards-:-REP                      
G24CV2OWRI COURT OF CIVIL APPEALS JUDGE, PLACE 2-:-Write-In-:-NON                             
G24CV2RHAN COURT OF CIVIL APPEALS JUDGE, PLACE 2-:-Chad Hanson-:-REP                          
G24CV3OWRI COURT OF CIVIL APPEALS JUDGE, PLACE 3-:-Write-In-:-NON                             
G24CV3RMOO COURT OF CIVIL APPEALS JUDGE, PLACE 3-:-Terry A. Moore-:-REP                       
G24PREDHAR PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES-:-Kamala D. Harris-:-DEM         
G24PREIKEN PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES-:-Robert F. Kennedy Jr.-:-IND    
G24PREIOLI PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES-:-Chase Oliver-:-IND             
G24PREISTE PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES-:-Jill Stein-:-IND               
G24PREOWRI PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES-:-Write-In-:-NON                 
G24PRERTRU PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES-:-Donald J. Trump-:-REP          
G24PSCOWRI PRESIDENT, PUBLIC SERVICE COMMISSION-:-Write-In-:-NON                              
G24PSCRCAV PRESIDENT, PUBLIC SERVICE COMMISSION-:-Twinkle Andress Cavanaugh-:-REP             
GCON01DHOL UNITED STATES REPRESENTATIVE, 1ST CONGRESSIONAL DISTRICT-:-Tom Holmes-:-DEM        
GCON01OWRI UNITED STATES REPRESENTATIVE, 1ST CONGRESSIONAL DISTRICT-:-Write-In-:-NON          
GCON01RMOO UNITED STATES REPRESENTATIVE, 1ST CONGRESSIONAL DISTRICT-:-Barry Moore-:-REP       
GCON02DFIG UNITED STATES REPRESENTATIVE, 2ND CONGRESSIONAL DISTRICT-:-Shomari Figures-:-DEM   
GCON02OWRI UNITED STATES REPRESENTATIVE, 2ND CONGRESSIONAL DISTRICT-:-Write-In-:-NON          
GCON02RDOB UNITED STATES REPRESENTATIVE, 2ND CONGRESSIONAL DISTRICT-:-Caroleene Dobson-:-REP  
GCON03OWRI UNITED STATES REPRESENTATIVE, 3RD CONGRESSIONAL DISTRICT-:-Write-In-:-NON          
GCON03RROG UNITED STATES REPRESENTATIVE, 3RD CONGRESSIONAL DISTRICT-:-Mike Rogers-:-REP       
GCON04OWRI UNITED STATES REPRESENTATIVE, 4TH CONGRESSIONAL DISTRICT-:-Write-In-:-NON          
GCON04RADE UNITED STATES REPRESENTATIVE, 4TH CONGRESSIONAL DISTRICT-:-Robert B. Aderholt-:-REP
GCON05OWRI UNITED STATES REPRESENTATIVE, 5TH CONGRESSIONAL DISTRICT-:-Write-In-:-NON          
GCON05RSTR UNITED STATES REPRESENTATIVE, 5TH CONGRESSIONAL DISTRICT-:-Dale Strong-:-REP       
GCON06DAND UNITED STATES REPRESENTATIVE, 6TH CONGRESSIONAL DISTRICT-:-Elizabeth Anderson-:-DEM
GCON06OWRI UNITED STATES REPRESENTATIVE, 6TH CONGRESSIONAL DISTRICT-:-Write-In-:-NON          
GCON06RPAL UNITED STATES REPRESENTATIVE, 6TH CONGRESSIONAL DISTRICT-:-Gary Palmer-:-REP       
GCON07DSEW UNITED STATES REPRESENTATIVE, 7TH CONGRESSIONAL DISTRICT-:-Terri A. Sewell-:-DEM   
GCON07OWRI UNITED STATES REPRESENTATIVE, 7TH CONGRESSIONAL DISTRICT-:-Write-In-:-NON          
GCON07RLIT UNITED STATES REPRESENTATIVE, 7TH CONGRESSIONAL DISTRICT-:-Robin Litaker-:-REP  


***al_2024_gen_cong_prec***
CONG_DIST  Congressional District                                                                          
   
                                                                     
## Processing Steps
Statewide election result totals in this file were compared against those found in the state's certification of election results (https://www.sos.alabama.gov/sites/default/files/election-2024/State%20Certification%20of%202024%20General%20Election.pdf). Totals matched in all instances for all contests.

The precinct boundary and election result files are split across two different files. The "_all_" file contains all the election results joined to precinct boundaries, but does not account for the congressional district-precinct splits identified in processing and as such, does not contain district assignments. The "_cong_" file contains congressional results at the most granular units for which data is available. Please note that in order to minimize superfluous splits, precinct splits are only made when a precinct contains votes for candidates in multiple districts, as such district assignments for precincts many not perfectly correspond to the districts themselves, particularly in large, uninhabited areas.

In certain cases, votes for particular Congressional candidates are counted in precincts that are not contained within the districts. When constructing the "_cong_" file, these precinct geometries are first verified, and if not believed to be incorrect, these additional votes are removed from the file. 97 votes for Cong 6 candidates in precincts 1030, 1070, 1100, 1130, 3290 and 3330 in Jefferson County. These votes are not removed from the "_all_" file. After running the splits, we examine the split areas to determine whether they appear to be real geographies that could in fact contain votes. After this check, the following precincts are removed: Clarke-:-GOSPORT FIRE-(CONG-07), Clarke-:-WALKER SPRNGS-(CONG-07), Jefferson-:-PREC 2180 - AVONDALE PUBLIC LI-(CONG-06), Jefferson-:-PREC 3015 - HOOVER MET SPORTS-(CONG-06), Jefferson-:-PREC 3280 - BROOKSIDE COMMUNIT-(CONG-06), Jefferson-:-PREC 4070 - TARRANT CITY HALL-(CONG-06), Jefferson-:-PREC 1010 - HUFFMAN BAPTIST CH-(CONG-06), Jefferson-:-PREC 1060 - SUN VALLEY ELEMENT-(CONG-06), Jefferson-:-PREC 3130 - SHADES CREST BAPTI-(CONG-06). Following all this processing, the totals in the "_cong_" file are lower than those in the "_all_" file by the following amounts: {'GCON07DSEW': 42, 'GCON06RPAL': 23, 'GCON06DAND': 93, 'GCON07RLIT': 14}.

There are a handful of splits small enough to not constitute the majority area of any census block or any census block with population. After examination, these precincts appear to be plausible areas and are kept in the file: Jefferson-:-PREC 5010 - HOOVER PARK & RECR-(CONG-07), Tuscaloosa-:-ALBERTA BAPT CH-(CONG-04), Jefferson-:-PREC 4090 - FULTONDALE FIRST B-(CONG-06), Jefferson-:-PREC 4125 - HOPE COMMUNITY CHU-(CONG-06), Clarke-:-JACKSON CITY HALL-(CONG-07), Jefferson-:-PREC 3040 - PRINCE OF PEACE CA-(CONG-06).

Due to new polling locations or name changes, some precinct names do not exactly match those found in the 2022 precinct file, these changes were all verified with documentation from the counties or, if no documentation was obtained, by checking against the voter file. 

Every county's precincts have been checked against an individual-level voter file from December, 2024 with precinct assignments.

Lastly, the maup smart_repair function was run in order to clean the small overlaps and geographical gaps that occur from combining shapefiles from a number of different sources. 

Please direct questions related to processing this dataset to info@redistrictingdatahub.org.
