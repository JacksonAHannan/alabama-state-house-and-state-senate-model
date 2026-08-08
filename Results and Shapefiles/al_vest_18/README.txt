2018 Alabama precinct and election results shapefile.

## RDH Date retrieval
06/01/2021

## Sources
Election results from the Alabama Secretary of State Elections Division (https://www.sos.alabama.gov/alabama-votes/voter/election-data). 
Incorrect or incomplete data was replaced using the county canvass reports for the following counties: Dallas, Chilton, Covington, Escambia, Lauderdale, Monroe, Pickens, Russell.

Precinct shapefiles initially from the U.S. Census Bureau's 2020 Redistricting Data Program final release, except the following counties use shapefiles sourced from the respective county governments instead: Baldwin, Blount, Calhoun, Cullman, DeKalb, Franklin, Jefferson, Lee, Limestone, Madison, Marengo, Marshall, Mobile, Montgomery, Morgan, St. Clair, Shelby, Talladega, Tuscaloosa.

## Fields metadata

Vote Column Label Format
------------------------
Columns reporting votes follow a standard label pattern. One example is:
G16PREDCli
The first character is G for a general election, P for a primary, S for a special, and R for a runoff.
Characters 2 and 3 are the year of the election.
Characters 4-6 represent the office type (see list below).
Character 7 represents the party of the candidate.
Characters 8-10 are the first three letters of the candidate's last name.

Office Codes
A## - Ballot amendment, where ## is an identifier
AGR - Commissioner of Agriculture
ATG - Attorney General
AUD - Auditor
CFO - Chief Financial Officer
CHA - Council Chairman
COC - Corporation Commissioner
COM - Comptroller
CON - State Controller
COU - City Council Member
CSC - Clerk of the Supreme Court
DEL - Delegate to the U.S. House
GOV - Governor
H## - U.S. House, where ## is the district number. AL: at large.
HOD - House of Delegates, accompanied by a HOD_DIST column indicating district number
HOR - U.S. House, accompanied by a HOR_DIST column indicating district number
INS - Insurance Commissioner
LAB - Labor Commissioner
LND - Commissioner of Public/State Lands
LTG - Lieutenant Governor
MAY - Mayor
MNI - State Mine Inspector
PSC - Public Service Commissioner
PUC - Public Utilities Commissioner
RGT - State University Regent
SAC - State Appeals Court (in AL: Civil Appeals)
SBE - State Board of Education
SCC - State Court of Criminal Appeals
SOC - Secretary of Commonwealth
SOS - Secretary of State
SPI - Superintendent of Public Instruction
SPL - Commissioner of School and Public Lands
SSC - State Supreme Court
TAX - Tax Commissioner
TRE - Treasurer
UBR - University Board of Regents/Trustees/Governors
USS - U.S. Senate

Party Codes
D and R will always represent Democrat and Republican, respectively.
See the state-specific notes for the remaining codes used in a particular file; note that third-party candidates may appear on the ballot under different party labels in different states.

## Fields

G18GOVRIVE - Kay Ivey (Republican Party)
G18GOVDMAD - Walt Maddox (Democratic Party)
G18GOVOWRI - Write-in Votes

G18LTGRAIN - Will Ainsworth (Republican Party)
G18LTGDBOY - Will Boyd (Democratic Party)
G18LTGOWRI - Write-in Votes

G18ATGRMAR - Steve Marshall (Republican Party)
G18ATGDSIE - Joseph Siegelman (Democratic Party)
G18ATGOWRI - Write-in Votes

G18TRERMCM - John McMillan (Republican Party)
G18TREOWRI - Write-in Votes

G18AGRRPAT - Rick Pate (Republican Party)
G18AGROWRI - Write-in Votes

G18SOSRMER - John Merrill (Republican Party)
G18SOSDMIL - Heather Milam (Democratic Party)
G18SOSOWRI - Write-in Votes

G18AUDRZEI - Jim Zeigler (Republican Party)
G18AUDDJOS - Miranda Joseph (Democratic Party)
G18AUDOWRI - Write-in Votes

G18SSCRPAR - Tom Parker (Republican Party)
G18SSCDVAN - Robert S. Vance (Democratic Party)
G18SSCOWRI - Write-in Votes

G18SSCRSTE - Sarah Stewart (Republican Party)
G18SSCOWR2 - Write-in Votes

G18SSCRBRY - Tommy Bryan (Republican Party)
G18SSCOWR3 - Write-in Votes

G18SSCRSEL - William Sellers (Republican Party)
G18SSCOWR4 - Write-in Votes

G18SSCRMIT - Jay Mitchell (Republican Party)
G18SSCDSMA - Donna Wesson Smalley (Democratic Party)
G18SSCOWR5 - Write-in Votes

G18SACREDW - Christy Olinger Edwards (Republican Party)
G18SACOWRI - Write-in Votes

G18SACRHAN - Chad Hanson (Republican Party)
G18SACOWR2 - Write-in Votes

G18SACRMOO - Terry A. Moore (Republican Party)
G18SACOWR3 - Write-in Votes

G18SCCRMIN - Richard Minor (Republican Party)
G18SCCOWRI - Write-in Votes

G18SCCRMCC - Chris McCool (Republican Party)
G18SCCOWR2 - Write-in Votes

G18SCCRCOL - J. William "Bill" Cole (Republican Party)
G18SCCOWR3 - Write-in Votes

G18PSCRODE - Jeremy Oden (Republican Party)
G18PSCDMCC - Cara McClure (Democratic Party)
G18PSCOWRI - Write-in Votes

G18PSCRBEE - Chris Beeker (Republican Party)
G18PSCDPOW - Kari Powell (Democratic Party)
G18PSCOWR2 - Write-in Votes

## Processing Steps

Absentee and provisional ballots were reported countywide by all counties. These were distributed by candidate to precincts based on their share of the precinct-level reported vote.

Precinct boundaries were adjusted as appropriate to align with county maps, municipal boundaries, or commission districts. Precinct boundaries throughout the state were further reviewed with the voter registration file in effect for the November 2018 general election. Voting districts in nearly all counties were edited accordingly to align with reporting units in the 2018 election results. In many counties the resulting boundaries bear little resemblance to the 2020 Census VTDs. As these boundary revisions were so extensive only splits and merges are specified below by precinct.

Many precincts have outdated names in the Census VTDs. The Census VTDs also have at least some precinct names in wrong locations for the following counties: Clarke, Clay, Cleburne, Conecuh, Dallas, Escambia, Geneva, Greene, Jefferson, Lauderdale, Limestone, Marion, Marshall, Monroe, Perry, Randolph, Russell, Tallapoosa, Walker, Washington, Wilcox. Moreover, many precinct numbers and consequently the VTD GeoIDs are also incorrect throughout much of the state in the Census shapefiles. All precinct names and numbers have been edited to match the 2018 voter file.

The following splits and merges were made to align voting district boundaries with reporting units in the 2018 election results.

Barbour: Split Eufaula between Bevill/CC/Fellowship/McCoo/Sanford/WB
Calhoun: Add precinct splits to Beats 1, 4, 5, 9, 12, 13, 15, 19, 22
Cherokee: Split Friendship/Mt Calvary, McCord's/Rock Run, Mt Weisner/VFD #2
Choctaw: Split Cromwell/Halsell/Intersection
Clarke: Split Antioch/Grove Hill/Helwestern, Choctaw Bluff/Gainstown, Grove Hill NG/Whatley, Jackson/Skipper, Springfield/Thomasville; Merge Fulton FS/CH
Covington: Split Heath/Straughn, Pleasant Home/Wing
Cullman: Split Cullman City Hall/Civic Ctr/Conf Room/Courthouse
Dallas: Merge Marion Jct/New Friendship
Etowah: Merge Fords Valley/Hokes Bluff, Tabernacle/Walnut Park
Fayette: Split Browns-Glen Allen/Whites Chapel, Cole-Killingsworth/Paul Hubbert, Elm Grove/Studdard's, Fayette CC/Covin/YC, Lee-Belk/Palestine
Geneva: Split Bellwood/Chancellor, Flat Creek/Hacoda, Geneva CC/CH/CO/FC/NG, Hughes VH/Malvern, Lowery/Revels, Piney Grove/Samson/Samson Masonic, Slocomb/Tate
Jackson: Split Holly Springs/Pleasant Groves
Jefferson: Split 3020/3025 Pleasant Hill/McAdory; Merge 2350/5270 as Oxmoor Valley
Marion: Split Kimbrough N/S; Merge Hamilton N/S as ET Sims
Monroe: Split Chrysler/Mineola, Coleman/Excel, Franklin/Wainwright, Peterman/Philadelphia
Randolph: Split Bethel/Moores/Woodland, Cavers/Swagg, Corinth/Morrison, Midway/New Hope/Wedowee, Omaha/Tin Shop/Wehadkee, Rock Mills/Wilson
Russell: Split Courthouse/Golden Acres
Tallapoosa: Split Cooper/Duncan/Moncrief; Merge New Paces 901/902 to match county shapefile
Wilcox: Split National Guard Camden, Pine Apple Comm Ctr, Pine Apple AWIN, St Paul Church
Winston: Split Addison/Upshaw, Delmar/Natural Bridge, Haleyville/Neighborhood/Pebble/Waldrop, Lynn/Old Union, Nesmith/Helicon