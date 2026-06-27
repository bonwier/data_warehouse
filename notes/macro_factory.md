## HYPERLOCAL MACRO FACTORY: INSTITUTIONAL OPERATING MANUAL

The MacroFeatureEngineV2 class is a pure data calculator designed to ingest clean geographic/temporal keys and output an array of population-agnostic, structural risk variables. It is structurally split into four core analytical dimensions and a systemic shock layer.<br><br>

### Dimension 1: Passive Wealth & Migration Profile (IRS SOI)<br><br>

#### 1. Asset Density Ratio (ADR / Wealth Cushion)<br><br>

- **Mathematics:**
    
    <p style="text-align: center;"> \(\text{ADR}=\frac{\text{Dividends\ Received}+\text{Interest\ Received}}{\text{Wages\ and\ Salaries}}\)</p><br><br>

- **Interpretation:** Measures local consumer liquidity independent of active corporate payroll availability.<br><br>

- **Credit/Consulting Utility:** Ratios \(>0.15\) flag high-net-worth insulation zones. If a localized factory or dominant business shuts down, the local retail tax base and consumer service demand are anchored by deep passive capital cushions.<br><br>

#### 2. Tax Filer Density Velocity<br><br>

- **Mathematics:**

<p style="text-align: center;">\(\text{Velocity}=\frac{\text{Total\ Returns}_{t}-\text{Total\ Returns}_{t-5}}{\text{Total\ Returns}_{t-5}}\)</p><br><br>

- **Interpretation:** A 5-year longitudinal trailing panel tracking net taxpayer migration speed.<br><br>

- **Credit/Consulting Utility:** Positive velocity represents an expanding local tax foundation and business demand runway. Negative values signal structural demographic flight, eroding property value floors, and high systemic underwriting risk regardless of the individual project's strength.<br><br>

#### 3. Household Dependency Ratio (HDR)<br><br>

- **Mathematics:**

<p style="text-align: center;">\(\text{HDR}=\frac{\text{Total\ Exemptions}}{\text{Total\ Returns}}\)</p><br><br>

- **Interpretation:** Quantifies the average family dependency load per active tax filer.<br><br>

- **Credit/Consulting Utility:** High HDR metrics (\(>2.0\)) indicate that a significant portion of local household income is bound to fixed, essential family costs (food, healthcare, dependent care). This leaves the region highly sensitive to inflationary wage squeezes and localized economic disruptions.<br><br>


### Dimension 2: Labor Market Dynamics & Saturation (BLS LAUS/QCEW)<br><br>

#### 4. Labor Pool Structural Friction (Workforce Stability CV)<br><br>

- **Mathematics:**

<p style="text-align: center;">\(\text{CV}=\frac{\sigma (\text{Monthly\ Labor\ Force\ Counts}_{[t-4,t]})}{\mu (\text{Monthly\ Labor\ Force\ Counts}_{[t-4,t]})}\)</p><br><br>

- **Interpretation:** A 5-year rolling, population-agnostic Coefficient of Variation mapping monthly workforce size stability. Because it divides standard deviation by the mean, it normalizes volatility across rural towns and large cities, creating a clean index to map seasonal labor disruptions and workforce migration.<br><br>

- **Credit/Consulting Utility:** Scores \(<0.20\) reflect highly stable, predictable labor markets. Spikes \(>0.75\) indicate intense structural churn, seasonal resource dependency (e.g., agricultural/tourism), or rapid post-pandemic workforce reshuffling, raising operating cost risks for projects requiring stable talent acquisition.<br><br>

#### 5. Industry Market Saturation Location Quotient (LQ)<br><br>

- **Mathematics:**

<p style="text-align: center;">\(\text{LQ}=\frac{\text{Local\ Industry\ Establishments}\,/\,\text{Total\ Local\ Establishments}}{\text{National\ Industry\ Establishments}\,/\,\text{Total\ National\ Establishments}}\)</p><br><br>

- **Interpretation:** Measures relative local business concentration for a specific 4-digit NAICS code against the national baseline.<br><br>

- **Credit/Consulting Utility:** An LQ \(<1.0\) flags an underserved market with favorable borrower pricing power. An LQ \(>1.50\) triggers an automated credit policy alert for intensive competitive overcrowding, signaling potential margin compression and elevated default probability for new project entries.<br><br>


### Dimension 3: Advanced Regional Structure & Disconnect (BLS QCEW/IRS)<br><br>

#### 6. Local Industry Wage Diversification Index<br><br>

- **Mathematics:**

<p style="text-align: center;"> \(\text{Diversification}=1.0-\sum _{i=1}^{n}\left(\frac{\text{Wages\ of\ Industry}_{i}}{\text{Total\ Regional\ Payroll}}\right)^{2}\)</p><br><br>

- **Interpretation:** A normalized Herfindahl-Hirschman Index (HHI) proxy applied to all private sector wage distributions. Bounded strictly between \(0\) and \(1\).<br><br>

- **Credit/Consulting Utility:** Scores close to \(1.0\) indicate an exceptionally balanced regional payroll structure with high shock absorption. Low scores flag a "one-company town" vulnerability, where a single industry failure will trigger cascading retail and real estate default waves.<br><br>

#### 7. The Wage-to-Filer Disconnect Index<br><br>

- **Mathematics:**

<p style="text-align: center;"> \(\text{Disconnect}=\Delta _{5\text{Yr}}(\text{IRS\ Resident\ Wages\ Growth})-\Delta _{5\text{Yr}}(\text{BLS\ Local\ Business\ Payroll\ Growth})\)</p><br><br>

- **Interpretation:** Tracks the structural growth spread between where people live vs. where they work.<br><br>

- **Credit/Consulting Utility:** <br><br>
  - **Positive Score** (\(> +0.02\)): Commuter Bedroom Suburb. Importing wealth from adjacent employment centers. Very strong consumer/residential base, but low local corporate footprint.<br><br>
  - **Near-Zero Score** (\(\pm 0.02\)): Mature Corporate Hub. Local job creation and corporate expansions have successfully synchronized with residential population growth. <br><br>
  - **Negative Score** (\(< -0.02\)): Industrial Production Engine. Generating heavy local payrolls but leaking consumer wealth outward because workers commute in but live and shop elsewhere.<br><br>

### Dimension 4: Systemic Sovereign & State Shock Anchors (FRED/Census QWI)<br><br>

#### 8. Sovereign Yield Spread (T10Y2Y)<br><br>

 - **Interpretation:** The constant-maturity spread between the 10-Year and 2-Year US Treasury.Credit Application: A sustained inversion (\(<0.0\)) signals capital tightness and broad liquidity contraction. Institutional policy manually scales project debt-service cash reserve requirements by 1.25x to shield against macro funding failures.<br><br>

#### 9. State Coincident Activity Momentum<br><br>

- **Mathematics:**

<p style="text-align: center;"> \(\text{Momentum}=\frac{\text{State\ Coincident\ Index}_{t}-\text{State\ Coincident\ Index}_{t-1}}{\text{State\ Coincident\ Index}_{t-1}}\)</p><br><br>

- **Interpretation:** The 12-month acceleration vector of the Philadelphia Fed's Coincident Index, tracking true Gross State Product drift.Credit Application: Negative momentum indicates a project is fighting an overall state-level recessionary contraction, overriding automated local approvals for manual credit committee reviews.<br><br>

#### 10. State Private Labor Turnover (Separation Rate)<br><br>

- **Mathematics:**

<p style="text-align: center;"> \(\text{Turnover}=\frac{\text{Total\ Quarterly\ Private\ Separations}}{\text{Total\ Quarterly\ Private\ Employment\ Baseline}}\)</p><br><br>

- **Interpretation:** Vectorized, population-agnostic state industry turnover from Census QWI.Credit Application: Spikes map out systemic wage escalation stress, worker attrition volatility, and generalized input cost inflation across the target state.