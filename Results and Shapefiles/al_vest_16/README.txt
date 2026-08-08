2016 Alabama precinct and election results shapefile.

## RDH Date retrieval
06/01/2021

## Sources

Election results from the Alabama Secretary of State Elections Division (https://www.sos.alabama.gov/alabama-votes/voter/election-data). 
Incorrect or incomplete data was replaced using the county canvass reports for the following counties: Blount, Bullock, Dallas, Escambia, Greene, Hale, Jackson, Jefferson, Lamar, Lawrence, Marion, Pickens, Randolph, Russell, St. Clair, Shelby, Washington, Wilcox.

Precinct shapefiles primarily from the U.S. Census Bureau's 2020 Redistricting Data Program final release, except the following counties use shapefiles sourced from the respective county governments instead: Baldwin, Blount, Calhoun, Cullman, DeKalb, Franklin, Jefferson, Lee, Limestone, Madison, Marengo, Marshall, Mobile, Morgan, St. Clair, Shelby, Talladega, Tuscaloosa.

## Fields metadata

Vote Column Label Format
------------------------
Columns reporting votes follow a standard label pattern. One example is:
G16PREDCli
The first character is G for a general election, P for a primary, C for a caucus, R for a runoff, S for a special.
Characters 2 and 3 are the year of the election.
Characters 4-6 represent the office type (see list below).
Character 7 represents the party of the candidate.
Characters 8-10 are the first three letters of the candidate's last name.

Office Codes
AGR - Commissioner of Agriculture
ATG - Attorney General
AUD - Auditor
COM - Comptroller
COU - City Council Member
DEL - Delegate to the U.S. House
GOV - Governor
H## - U.S. House, where ## is the district number. AL: at large.
HOD - House of Delegates, accompanied by a HOD_DIST column indicating district number
HOR - U.S. House, accompanied by a HOR_DIST column indicating district number
INS - Commissioner of Insurance
LAB - Commissioner of Labor
LTG - Lieutenant Governor
LND - Commissioner of Public Lands
PRE - President
PSC - Public Service Commissioner
PUC - Public Utilities Commissioner
RGT - State University Regent
RRC - Railroad Commissioner
SAC - State Court of Appeals
SOS - Secretary of State
SOV - Senate of Virginia, accompanied by a SOV_DIST column indicating district number
SPI - Superintendent of Public Instruction
SSC - State Supreme Court
TRE - Treasurer
USS - U.S. Senate

Party Codes
D and R will always represent Democrat and Republican, respectively.
See the state-specific notes for the remaining codes used in a particular file; note that third-party candidates may appear on the ballot under different party labels in different states.

## Fields

G16PRERTRU - Donald J. Trump (Republican Party)
G16PREDCLI - Hillary Clinton (Democratic Party)
G16PRELJOH - Gary Johnson (Libertarian Party)
G16PREGSTE - Jill Stein (Green Party)
G16PREOWRI - Write-in Votes

G16USSRSHE - Richard Shelby (Republican Party)
G16USSDCRU - Ron Crumpton (Democratic Party)
G16USSOWRI - Write-in Votes

G16SSCRBOL - Michael Bolin (Republican Party)
G16SSCOWRI - Write-in Votes

G16SSCRWIS - Kelli Wise (Republican Party)
G16SSCOWR2 - Write-in Votes

G16SSCRPAR - Tom Parker (Republican Party)
G16SSCOWR3 - Write-in Votes

G16PSCRCAV - Twinkle Andress Cavanaugh (Republican Party)
G16PSCOWRI - Write-in Votes

## Processing Steps

Absentee and provisional ballots were reported countywide in all counties. These were distributed by candidate to precincts based on their share of the precinct-level reported vote. Mobile County also reported only countywide totals for write in votes. These were distributed to precincts based on the difference between the number of ballots cast and the total votes reported for named candidates.

Note that the precinct results from DeKalb County add up to a higher total number of votes than the countywide totals certified by the state canvass. At the presidential level the difference is: Clinton (D) 60, Trump (R) 374, Johnson (L) 11, Stein (G) 4, Write In 3.

Precinct boundaries were adjusted as appropriate to align with county maps, municipal boundaries, or commission districts. Precinct boundaries throughout the state were further reviewed with the voter registration file in effect for the November 2016 general election. Voting districts in nearly all counties were edited accordingly to align with reporting units in the 2016 election results. In many counties the resulting boundaries bear little resemblance to the 2020 Census VTDs. As these boundary revisions were so extensive only splits and merges are specified below by precinct.

Many precincts have outdated names in the Census VTDs. The Census VTDs also have at least some precinct names in wrong locations for the following counties: Clarke, Clay, Cleburne, Conecuh, Dallas, Escambia, Geneva, Greene, Jefferson, Lauderdale, Limestone, Marion, Marshall, Monroe, Perry, Randolph, Russell, Tallapoosa, Walker, Washington, Wilcox. Moreover, many precinct numbers and consequently the VTD GeoIDs are also incorrect throughout much of the state in the Census shapefiles. All precinct names and numbers have been edited to match the 2016 voter file.

The following splits and merges were made to align voting district boundaries with reporting units in the 2016 election results.

Autauga: Merge Boone's Chapel/County Line
Barbour: Split Eufaula between Bevill/CC/Fellowship/McCoo/Sanford/WB
Calhoun: Add precinct splits to Beats 1, 4, 5, 9, 12, 13, 15, 19, 22
Cherokee: Split Friendship/Mt Calvary, McCord's/Rock Run, Mt Weisner/VFD #2
Choctaw: Split Cromwell/Halsell/Intersection
Clarke: Split Antioch/Grove Hill/Helwestern, Choctaw Bluff/Gainstown, Grove Hill NG/Whatley, Jackson/Skipper, Springfield/Thomasville; Merge Fulton FS/CH
Covington: Split Heath/Straughn, Pleasant Home/Wing
Cullman: Split Cullman City Hall/Civic Ctr/Conf Room/Courthouse
Dallas: Merge Marion Jct/New Friendship
Elmore: Merge Grandview Pines/Nazarene
Fayette: Split Browns Glen Allen/Whites Chapel, Cole Killingsworth/New River, Elm Grove/Studdards, Fayette CC/Covin/YC, Lee-Belk/Oak Ridge
Geneva: Split Bellwood/Chancellor, Flat Creek/Hacoda, Geneva CC/CH/CO/FC/NG, Hughes VH/Malvern, Lowery/Revels, Piney Grove/Samson/Samson Masonic, Slocomb/Tate
Houston: Split Enterprise/Lovetown; Merge Mt Gilead/Water & Electric
Jackson: Split Holly Springs/Pleasant Groves
Jefferson: Split 1350/1400 CJ Donald/Fairfield; Merge 2350/5270 as Oxmoor Valley, 3010/3015 as Hunter St
Lee: Split Boykin/National Guard
Marengo: Split Aimwell/Sweet Water, Taylorville/Thomaston
Marion: Split Kimbrough N/S; Merge Hamilton N/S as ET Sims
Marshall: Split Arab Comm Ctr/Rec Ctr, Guntersville/Warrenton
Monroe: Split Chrysler/Mineola, Coleman/Excel, Franklin/Wainwright, Peterman/Philadelphia
Randolph: Split Bethel/Moores/Woodland, Cavers/Swagg, Corinth/Morrison, Midway/New Hope/Wedowee, Omaha/Tin Shop/Wehadkee, Rock Mills/Wilson
Russell: Split Courthouse/Golden Acres
Tallapoosa: Split Cooper/Duncan/Moncrief; Merge New Paces 901/902 to match county shapefile
Wilcox: Split National Guard Camden, Pine Apple Comm Ctr, Pine Apple AWIN, St Paul Church
Winston: Split Addison/Upshaw, Delmar/Natural Bridge, Haleyville/Neighborhood/Pebble/Waldrop, Lynn/Old Union, Nesmith/Helicon