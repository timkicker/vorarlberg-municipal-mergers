PY = uv run python src/gf
# steps that need inputs placed by hand (DATA.md); without them the file from the repository stays in data/derived
KEEP = || echo "  skipped: needs inputs placed by hand (DATA.md), data/derived keeps the file from the repository"

.PHONY: data results figures

data:
	$(PY)/fetch.py

results:
	$(PY)/adjacency.py
	$(PY)/costs.py
	$(PY)/styria_transition_net.py
	$(PY)/commuters.py
	$(PY)/styria_control.py
	$(PY)/free_riding.py
	$(PY)/coop2016.py
	$(PY)/party_labels.py
	$(PY)/personnel.py $(KEEP)
	$(PY)/school_closures.py
	$(PY)/styria_checks.py
	$(PY)/styria_clean_controls.py
	$(PY)/styria_compare.py
	$(PY)/styria_elections.py
	$(PY)/styria_euros.py
	$(PY)/styria_fag.py
	$(PY)/styria_gross_no14.py
	$(PY)/styria_group8.py
	$(PY)/styria_groups.py
	$(PY)/styria_names.py
	$(PY)/styria_no_buildings.py
	$(PY)/styria_outcomes.py
	$(PY)/styria_transfers.py
	$(PY)/styria_transfers_2024.py $(KEEP)
	$(PY)/styria_transition.py
	$(PY)/styria_voluntary.py
	$(PY)/overview.py
	$(PY)/styria.py
	$(PY)/scale_weighted.py
	$(PY)/regions.py
	$(PY)/cuts_outside.py
	$(PY)/pareto.py
	$(PY)/sensitivity.py
	$(PY)/turnout.py
	$(PY)/turnout_split.py
	$(PY)/pop2050.py
	$(PY)/coop_areas.py
	$(PY)/coop_montafon.py
	$(PY)/elections.py
	$(PY)/ratio.py
	$(PY)/roads.py
	$(PY)/fire_brigades.py
	$(PY)/mayors.py
	$(PY)/status_quo_trend.py
	$(PY)/building_land.py
	$(PY)/club_grants.py $(KEEP)
	$(PY)/council_seats.py
	$(PY)/cross_border.py
	$(PY)/debt.py
	$(PY)/holdings.py
	$(PY)/state_grants.py
	$(PY)/mayor_pay.py
	$(PY)/second_homes.py
	$(PY)/street_names.py
	$(PY)/structural_fund.py
	$(PY)/unions.py
	$(PY)/border_pairs.py
	$(PY)/fag.py
	$(PY)/fees.py $(KEEP)
	$(PY)/investment.py $(KEEP)
	$(PY)/size_trends.py $(KEEP)
	$(PY)/tourism_budget.py $(KEEP)
	$(PY)/organs_styria_check.py
	$(PY)/childcare.py $(KEEP)
	$(PY)/dissimilarity.py
	$(PY)/fiscal_stress.py
	$(PY)/infrastructure.py $(KEEP)
	$(PY)/payroll_tax.py
	$(PY)/resort_class.py
	$(PY)/structural_fund_bmf.py
	$(PY)/mittelberg.py
	$(PY)/profiles.py
	$(PY)/robustness.py
	$(PY)/seat_distance.py
	$(PY)/transit.py $(KEEP)
	$(PY)/voluntary.py
	$(PY)/balance.py
	$(PY)/base_amount.py $(KEEP)
	$(PY)/boundaries.py
	$(PY)/elected_bodies.py $(KEEP)
	$(PY)/grant_clawback.py $(KEEP)
	$(PY)/referendum_hurdle.py
	$(PY)/savings_2024.py $(KEEP)
	$(PY)/savings_2024_low.py
	$(PY)/styria_no2014.py
	$(PY)/total_spending_2024.py $(KEEP)
	$(PY)/styria_bootstrap.py
	$(PY)/services.py
	$(PY)/size_duties.py
	$(PY)/social_fund.py
	$(PY)/tourism.py
	$(PY)/veto_pattern.py
	$(PY)/water_bodies.py
	$(PY)/size_grants.py $(KEEP)
	$(PY)/local_heads.py
	$(PY)/balance_2024.py
	$(PY)/balance_2024.py --low
	$(PY)/merger_grant.py
	$(PY)/mittelberg_2024.py
	$(PY)/per_capita.py
	$(PY)/figures.py
	$(PY)/maps.py
	$(PY)/figure_money.py
	uv run pytest

figures:
	$(PY)/figures.py
	$(PY)/maps.py
	$(PY)/figure_money.py
