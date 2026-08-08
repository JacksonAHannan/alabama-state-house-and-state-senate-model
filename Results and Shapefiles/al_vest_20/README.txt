2020 Alabama precinct and election results shapefile.

## RDH Date retrieval
06/01/2021

## Sources
Election results from the Alabama Secretary of State Elections Division (https://www.sos.alabama.gov/alabama-votes/voter/election-data). 
Precinct shapefiles initially from the U.S. Census Bureau's 2020 Redistricting Data Program final release, except the following counties use shapefiles sourced from the respective county governments instead: Baldwin, Blount, Calhoun, Cullman, DeKalb, Franklin, Jefferson, Lee, Limestone, Madison, Marengo, Marshall, Mobile, Morgan, St. Clair, Shelby, Talladega, Tuscaloosa.

## Fields metadata

Vote Column Label Format
------------------------
Columns reporting votes follow a standard label pattern. One example is:
G20PRERTRU
The first character is G for a general election, C for recount results, P for a primary, S for a special, and R for a runoff.
Characters 2 and 3 are the year of the election.
Characters 4-6 represent the office type (see list below).
Character 7 represents the party of the candidate.
Characters 8-10 are the first three letters of the candidate's last name.

Office Codes

COC - Corporation Commissioner
COU - City Council Member
DEL - Delegate to the U.S. House
GOV - Governor
H## - U.S. House, where ## is the district number. AL: at large.
PRE - President
PSC - Public Service Commissioner
SAC - State Appeals Court (in AL: Civil Appeals)
SCC - State Court of Criminal Appeals
USS - U.S. Senate

Party Codes
D and R will always represent Democrat and Republican, respectively.
See the state-specific notes for the remaining codes used in a particular file; note that third-party candidates may appear on the ballot under different party labels in different states.

## Fields

G20PRERTRU - Donald J. Trump (Republican Party)
G20PREDBID - Joseph R. Biden (Democratic Party)
G20PRELJOR - Jo Jorgensen (Libertarian Party)
G20PREOWRI - Write-in Votes

G20USSRTUB - Tommy Tuberville (Republican Party)
G20USSDJON - Doug Jones (Democratic Party)
G20USSOWRI - Write-in Votes

G20SSCRSHA - Greg Shaw (Republican Party)
G20SSCOWRI - Write-in Votes

G20SSCRMEN - Brad Mendheim (Republican Party)
G20SSCOWR2 - Write-in Votes

G20SACRTHO - William C. "Bill" Thompson (Republican Party)
G20SACOWRI - Write-in Votes

G20SACRFRI - Matt Fridy (Republican Party)
G20SACOWR2 - Write-in Votes

G20SCCRWIN - Mary Windom (Republican Party)
G20SCCOWRI - Write-in Votes

G20SCCRKEL - Beth Kellum (Republican Party)
G20SCCOWR2 - Write-in Votes

G20PSCRCAV - Twinkle Andress Cavanaugh (Republican Party)
G20PSCDCAS - Laura Casey (Democratic Party)
G20PSCOWRI - Write-in Votes

## Processing Steps

Absentee and provisional ballots were reported countywide in all counties. These were distributed by candidate to precincts based on their share of the precinct-level reported vote.

Precinct boundaries were adjusted as appropriate to align with county maps, municipal boundaries, or commission districts. Precinct boundaries throughout the state were further reviewed with the voter registration file in effect for the November 2020 general election. Voting districts in nearly all counties were edited accordingly to align with reporting units in the 2020 election results. In many counties the resulting boundaries bear little resemblance to the 2020 Census VTDs. As these boundary revisions were so extensive only splits and merges are specified below by precinct.

Many precincts have outdated names in the Census VTDs. The Census VTDs also have at least some precinct names in wrong locations for the following counties: Clarke, Clay, Cleburne, Conecuh, Dallas, Escambia, Geneva, Greene, Jefferson, Lauderdale, Limestone, Marion, Marshall, Monroe, Perry, Randolph, Russell, Tallapoosa, Walker, Washington, Wilcox. Moreover, many precinct numbers and consequently the VTD GeoIDs are also incorrect throughout much of the state in the Census shapefiles. All precinct names and numbers have been edited to match the 2020 voter file.

The following splits and merges were made to align voting district boundaries with reporting units in the 2020 election results.

Barbour: Split Eufaula between Bevill/CC/Fellowship/McCoo/Sanford/WB
Calhoun: Add precinct splits to Beats 1, 4, 5, 9, 12, 13, 15, 19, 22
Cherokee: Split Friendship/Mt Calvary, McCord's/Rock Run, Mt Weisner/VFD #2
Choctaw: Split Cromwell/Halsell/Intersection
Clarke: Split Antioch/Grove Hill/Helwestern, Choctaw Bluff/Gainstown, Grove Hill NG/Whatley, Jackson/Skipper, Springfield/Thomasville; Merge Fulton FS/CH
Colbert: Merge Mynot into Allsboro/Cherokee
Covington: Split Heath/Straughn, Pleasant Home/Wing
Cullman: Split Cullman City Hall/Civic Ctr/Conf Room/Courthouse
Dallas: Merge Marion Jct/New Friendship
DeKalb: Merge Antioch/Fyffe, Pea Ridge into Hammondville/Henagar/Ider, Five Points/Senior Center
Etowah: Merge Fords Valley/Hokes Bluff, Tabernacle/Walnut Park
Fayette: Split Browns-Glen Allen/Whites Chapel, Cole-Killingsworth/Paul Hubbert, Fayette CC/Covin/YC, Lee-Belk/Palestine
Geneva: Split Bellwood/El Bethel, Flat Creek/Hacoda, Hughes VH/Malvern, Lowery/Revels, Piney Grove/Samson, Slocomb/Tate
Jackson: Merge Aspel/Limrock, Bishop Hall/Estill Fork, Christian Home/Flat Rock, Garth/Trenton, Hambrick/Hollytree/Princeton
Jefferson: Split 3030/3035 Bethel Baptist/Pleasant Grove; Merge 1120/1260 as Robinson Elementary, 2350/5270 as Oxmoor Valley
Marion: Split Kimbrough N/S; Merge Hamilton N/S as ET Sims
Monroe: Split Chrysler/Mineola, Coleman/Excel, Franklin/Wainwright, Peterman/Philadelphia
Randolph: Split Bethel/Moores/Woodland, Cavers/Swagg, Corinth/Morrison, Midway/New Hope/Wedowee, Omaha/Tin Shop/Wehadkee, Rock Mills/Wilson
Russell: Split Courthouse/Golden Acres
Tallapoosa: Split Cooper/Duncan/Moncrief; Merge New Paces 901/902 to match county shapefile
Wilcox: Split National Guard Camden, Pine Apple Comm Ctr, Pine Apple AWIN, St Paul Church
Winston: Split Addison/Upshaw, Delmar/Natural Bridge, Haleyville/Neighborhood/Pebble/Waldrop, Lynn/Old Union, Nesmith/Helicon