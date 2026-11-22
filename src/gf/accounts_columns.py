"""Column names of the Statistics Austria open data files, kept as in the source."""

# gemhh_at_2000_2019.csv, basic municipal budget data
COL_INHABITANTS = "F-EINWOHNER"  # inhabitants
COL_ORDINARY_SPENDING = "F-SUMME_1"  # ordinary budget, spending
COL_ORDINARY_REVENUE = "F-SUMME_2"  # ordinary budget, revenue
COL_EXTRAORDINARY_SPENDING = "F-SUMME_5"  # extraordinary budget, spending
COL_EXTRAORDINARY_REVENUE = "F-SUMME_6"  # extraordinary budget, revenue
COL_OWN_REVENUE = "F-SEIN_SUMME"  # own revenue, total
COL_FEES = "F-SEIN_GEBUEHREN"  # own revenue, fees
COL_TAX_SHARES = "F-SEIN_ERTRAG"  # shares of federal taxes
COL_DEBT = "F-SCHU_SUMME"  # total debt

# gemua_at_*.csv, municipal finances by sub-section
COL_SPENDING = "F-LJ_1"  # spending of the year
COL_REVENUE = "F-LJ_2"  # revenue of the year

# tour_ua_land*.csv, tourism
COL_OVERNIGHT_STAYS = "F-UEB"  # overnight stays

# vpi15.csv, consumer price index 2015
COL_CPI = "F-VPIMZBM"  # index value

# bevstand_*.csv and other STATcube exports, population
COL_POPULATION_JAN1 = "F-ISIS-1"  # population at 1 January
