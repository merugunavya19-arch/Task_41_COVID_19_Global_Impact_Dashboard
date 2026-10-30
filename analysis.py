"""Dataset-driven COVID data cleaner, metric calculator and report generator."""
from pathlib import Path
import argparse, json, warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

ALIASES = {
 'location':['location','country','countries','entity','nation'], 'date':['date','day','reported_date'],
 'new_cases':['new_cases','daily_new_cases','daily_cases','new cases'], 'total_cases':['total_cases','cumulative_cases','confirmed_cases','cases'],
 'new_deaths':['new_deaths','daily_new_deaths','daily_deaths'], 'total_deaths':['total_deaths','cumulative_deaths','deaths'],
 'people_vaccinated':['people_vaccinated','vaccinated_people','people_vaccinated_once'],
 'people_fully_vaccinated':['people_fully_vaccinated','fully_vaccinated'], 'population':['population','pop']}
NUMERIC=set(ALIASES)-{'location','date'}
def norm(s): return ''.join(c.lower() for c in str(s) if c.isalnum())
def find_col(cols, aliases):
    lookup={norm(c):c for c in cols}
    for a in aliases:
        if norm(a) in lookup: return lookup[norm(a)]
    return None

def run(input_path):
    src=Path(input_path)
    if not src.exists(): raise FileNotFoundError(f"Dataset not found: {src}. Place your file at data/raw/covid.csv or pass --input.")
    df=pd.read_csv(src, low_memory=False)
    original_rows=len(df); original_cols=list(df.columns)
    mapping={k:find_col(df.columns,v) for k,v in ALIASES.items()}
    if not mapping['location'] or not mapping['date']:
        raise ValueError(f"Could not identify required country/date columns. Columns found: {original_cols}. Edit ALIASES in analysis.py for your dataset.")
    # Rename recognized fields to consistent, documented names; preserve other source columns.
    ren={v:k for k,v in mapping.items() if v and v!=k}
    df=df.rename(columns=ren)
    before_dup=len(df); df=df.drop_duplicates().copy(); duplicates=before_dup-len(df)
    df['date']=pd.to_datetime(df['date'], errors='coerce', utc=True).dt.tz_convert(None)
    bad_dates=int(df['date'].isna().sum()); df=df.dropna(subset=['date','location'])
    df['location']=df['location'].astype(str).str.strip()
    for c in NUMERIC:
        if c in df:
            df[c]=pd.to_numeric(df[c], errors='coerce')
            # Preserve negative daily revisions; invalid negative cumulative/population values become missing.
            if c in {'total_cases','total_deaths','population','people_vaccinated','people_fully_vaccinated'}:
                df.loc[df[c]<0,c]=np.nan
    df=df.sort_values(['location','date']).reset_index(drop=True)
    if 'new_cases' in df:
        df['new_cases_7d_avg']=df.groupby('location')['new_cases'].transform(lambda s:s.rolling(7,min_periods=1).mean())
    if {'total_cases','total_deaths'}<=set(df.columns):
        df['case_fatality_rate_pct']=np.where(df.total_cases>0,df.total_deaths/df.total_cases*100,np.nan)
    if {'total_cases','population'}<=set(df.columns):
        df['cases_per_million']=np.where(df.population>0,df.total_cases/df.population*1e6,np.nan)
    if {'people_vaccinated','population'}<=set(df.columns):
        df['vaccination_coverage_pct']=np.where(df.population>0,df.people_vaccinated/df.population*100,np.nan)
    # Doubling time: rolling-back 7-day interval, only positive growth and >= 7 elapsed days.
    if 'total_cases' in df:
        def doubling(g):
            vals=[]
            dates=g.date
            for i,row in g.iterrows():
                past=g[(g.date<=row.date-pd.Timedelta(days=7)) & (g.total_cases>0)]
                cur=row.total_cases
                if pd.notna(cur) and cur>0 and len(past):
                    old=past.iloc[-1].total_cases; days=(row.date-past.iloc[-1].date).days
                    vals.append(days*np.log(2)/np.log(cur/old) if cur>old and days>0 else np.nan)
                else: vals.append(np.nan)
            return pd.Series(vals,index=g.index)
        df['doubling_time_days']=df.groupby('location',group_keys=False).apply(doubling, include_groups=False).reset_index(level=0,drop=True) if False else np.nan
        # Explicit group iteration works across supported pandas versions.
        for _,g in df.groupby('location',sort=False): df.loc[g.index,'doubling_time_days']=doubling(g).values
    out=Path('data/processed'); out.mkdir(parents=True,exist_ok=True)
    df.to_csv(out/'COVID_19_Cleaned_Data.csv',index=False)
    report=Path('reports'); figdir=report/'figures'; figdir.mkdir(parents=True,exist_ok=True)
    sns.set_theme(style='whitegrid'); countries=df.location.nunique()
    def plot_series(col,title,ylabel,file):
        if col not in df: return
        top=df.groupby('location')[col].max().nlargest(8).index
        sub=df[df.location.isin(top)].dropna(subset=[col])
        if sub.empty:return
        fig,ax=plt.subplots(figsize=(11,5))
        for country,g in sub.groupby('location'): ax.plot(g.date,g[col],label=country,linewidth=1.5)
        ax.set(title=title,xlabel='Date',ylabel=ylabel); ax.legend(loc='best',fontsize=8); fig.tight_layout(); fig.savefig(figdir/file,dpi=150); plt.close(fig)
    plot_series('new_cases','Daily new COVID-19 cases (top 8 by peak)','Daily cases','daily_new_cases.png')
    plot_series('new_cases_7d_avg','Daily cases and 7-day rolling average','Cases','daily_cases_rolling_average.png')
    plot_series('total_deaths','Cumulative reported deaths over time','Total deaths','total_deaths.png')
    def bar_metric(col,title,label,file):
        if col not in df:return
        z=df.sort_values('date').groupby('location').tail(1).dropna(subset=[col]).nlargest(15,col)
        if z.empty:return
        fig,ax=plt.subplots(figsize=(10,6)); sns.barplot(data=z,x=col,y='location',ax=ax,color='#247BA0'); ax.set(title=title,xlabel=label,ylabel='Country'); fig.tight_layout();fig.savefig(figdir/file,dpi=150);plt.close(fig)
    bar_metric('total_cases','Countries by latest reported cumulative cases','Cases','country_cases.png')
    bar_metric('cases_per_million','Countries by latest cases per million','Cases per million','cases_per_million.png')
    bar_metric('vaccination_coverage_pct','Countries by latest vaccination coverage','Coverage (%)','vaccination_coverage.png')
    missing=df.isna().sum().sort_values(ascending=False)
    lines=['# Dataset profile and computed insights','',f'- Source file: `{src}`',f'- Rows after removing duplicates/invalid dates: {len(df):,} (input rows: {original_rows:,})',f'- Source columns: {len(original_cols)}; countries/entities: {countries}',f'- Date range: {df.date.min().date()} to {df.date.max().date()}',f'- Exact duplicate rows removed: {duplicates:,}',f'- Rows removed for missing/unparseable country/date: {bad_dates:,}',f'- Recognized source fields: '+', '.join(f'{k} ← {v}' for k,v in mapping.items() if v),'','## Data-dependent observations','']
    if 'total_cases' in df:
        z=df.sort_values('date').groupby('location').tail(1).dropna(subset=['total_cases'])
        if len(z):
            r=z.loc[z.total_cases.idxmax()]; lines.append(f"- Highest latest cumulative cases among entities in this file: **{r.location}** ({r.total_cases:,.0f}, as of {r.date.date()}).")
    if 'cases_per_million' in df:
        z=df.sort_values('date').groupby('location').tail(1).dropna(subset=['cases_per_million'])
        if len(z):
            r=z.loc[z.cases_per_million.idxmax()];lines.append(f"- Highest latest cases per million among entities with valid population: **{r.location}** ({r.cases_per_million:,.1f}, as of {r.date.date()}).")
    if 'vaccination_coverage_pct' in df:
        z=df.sort_values('date').groupby('location').tail(1).dropna(subset=['vaccination_coverage_pct'])
        if len(z):
            r=z.loc[z.vaccination_coverage_pct.idxmax()];lines.append(f"- Highest latest first-dose vaccination coverage among entities with population: **{r.location}** ({r.vaccination_coverage_pct:.1f}%, as of {r.date.date()}).")
    if len(lines)<15: lines.append('- No additional insight is stated unless supported by recognized fields and valid observations.')
    lines += ['', '## Cleaning notes', '- Dates parsed as UTC then stored without timezone; unparseable dates are excluded.', '- Duplicate rows removed; numeric fields coerced; missing values are not imputed.', '- Negative cumulative counts, vaccination counts, and population are set to missing; negative daily values are preserved as possible revisions.', '- The seven-day average uses up to seven available rows, not necessarily seven consecutive calendar days.', '- This file may be synthetic or incomplete; source provenance was not established by the project. Do not represent it as official statistics without verifying the source.','', '## Missing values (top 20 columns)','']
    lines += [f'- `{c}`: {n:,} missing ({n/len(df)*100:.1f}%)' for c,n in missing.head(20).items()]
    (report/'insights.md').write_text('\n'.join(lines)+'\n')
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        elems=[Paragraph('COVID-19 Global Impact Dashboard',getSampleStyleSheet()['Title']),Spacer(1,8),Paragraph('Objective: explore the supplied dataset for case, death, and vaccination patterns. Data source: '+str(src)+'. This summary is generated from the dataset supplied by the user; provenance must be independently verified.',getSampleStyleSheet()['BodyText']),Spacer(1,8)]
        for line in lines[2:]:
            if line.startswith('- '): elems.append(Paragraph(line[2:].replace('&','&amp;'),getSampleStyleSheet()['BodyText']));elems.append(Spacer(1,3))
        for f in [figdir/'daily_cases_rolling_average.png',figdir/'country_cases.png']:
            if f.exists(): elems += [Spacer(1,6),Image(str(f),width=6.3*inch,height=2.4*inch)]
        SimpleDocTemplate(str(report/'COVID_19_Executive_Summary.pdf'),pagesize=letter,rightMargin=36,leftMargin=36,topMargin=30,bottomMargin=30).build(elems)
    except Exception as e: warnings.warn(f'PDF not generated (install reportlab): {e}')
    print(f'Input rows: {original_rows}; cleaned rows: {len(df)}; countries/entities: {countries}; columns: {len(df.columns)}')
    print(f'Cleaned CSV: {out}/COVID_19_Cleaned_Data.csv; insights: reports/insights.md')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',default='data/raw/covid.csv');run(p.parse_args().input)
