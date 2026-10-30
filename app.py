from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title='COVID-19 Global Impact Dashboard',page_icon=None,layout='wide')
st.markdown('''<style>.stApp{background:#f4f7fb}.block-container{padding-top:1.4rem}.metric-card{background:white;padding:14px;border-radius:10px}</style>''',unsafe_allow_html=True)
st.title('COVID-19 Global Impact Dashboard')
st.caption('Explore cases, deaths and vaccination metrics in the dataset you provide. Values reflect the selected filters and dataset only.')
path=Path('data/processed/COVID_19_Cleaned_Data.csv')
if not path.exists():
    st.warning('No cleaned dataset found yet. Add your source file as `data/raw/covid.csv`, run `python analysis.py --input data/raw/covid.csv`, then refresh this page.')
    st.stop()
df=pd.read_csv(path,parse_dates=['date'])
if not {'location','date'}<=set(df.columns): st.error('Cleaned file is missing required location/date columns. Run analysis.py again.');st.stop()
lo,hi=df.date.min().date(),df.date.max().date()
with st.sidebar:
    st.header('Filters')
    countries=sorted(df.location.dropna().unique())
    selected=st.multiselect('Country / entity',countries,default=countries[:min(8,len(countries))])
    dates=st.date_input('Date range',value=(lo,hi),min_value=lo,max_value=hi)
    if len(dates)==2: start,end=dates
    else: start=end=dates[0]
filtered=df[df.location.isin(selected) & df.date.dt.date.between(start,end)]
if filtered.empty: st.info('No rows match the selected filters.');st.stop()
latest=filtered.sort_values('date').groupby('location',as_index=False).tail(1)
def total(k): return latest[k].sum(min_count=1) if k in latest else None
k1,k2,k3=st.columns(3)
for col,label,val,fmt in [(k1,'Total COVID-19 Cases',total('total_cases'),'{:,.0f}'),(k2,'Total COVID-19 Deaths',total('total_deaths'),'{:,.0f}')]:
    col.metric(label,fmt.format(val) if pd.notna(val) else 'Not available')
coverage=None
if {'people_vaccinated','population'}<=set(latest.columns):
    numerator=latest.people_vaccinated.sum(min_count=1);denominator=latest.population.sum(min_count=1)
    coverage=numerator/denominator*100 if pd.notna(numerator) and pd.notna(denominator) and denominator>0 else None
k3.metric('Vaccination Coverage',f'{coverage:.1f}%' if coverage is not None else 'Not available')
if {'new_cases','new_cases_7d_avg'}<=set(filtered):
    fig=px.line(filtered,x='date',y=['new_cases','new_cases_7d_avg'],color='location',title='Daily New Cases and 7-Day Rolling Average',labels={'value':'Cases','date':'Date','variable':'Series','location':'Country / entity'});st.plotly_chart(fig,use_container_width=True)
if 'total_deaths' in filtered:
    fig=px.line(filtered,x='date',y='total_deaths',color='location',title='Total Deaths Over Time',labels={'total_deaths':'Total deaths','date':'Date','location':'Country / entity'});st.plotly_chart(fig,use_container_width=True)
metric=next((c for c in ['cases_per_million','total_cases','vaccination_coverage_pct'] if c in filtered),None)
if metric:
    latest=filtered.sort_values('date').groupby('location',as_index=False).tail(1).dropna(subset=[metric]).sort_values(metric,ascending=False).head(20)
    if not latest.empty:
        fig=px.bar(latest,x=metric,y='location',orientation='h',title={'cases_per_million':'Country Comparison: Cases per Million','total_cases':'Country Comparison: Total Cases','vaccination_coverage_pct':'Country Comparison: Vaccination Coverage'}[metric],labels={metric:metric.replace('_',' ').title(),'location':'Country / entity'});fig.update_layout(yaxis={'categoryorder':'total ascending'});st.plotly_chart(fig,use_container_width=True)
with st.expander('Dataset caveats'):
    st.write('Missing values are not imputed. Population-based metrics are unavailable without valid population data. The dataset provenance is not verified here; determine whether it is official or synthetic before describing results.')
st.download_button('Download filtered data',filtered.to_csv(index=False).encode('utf-8'),file_name='COVID_19_filtered.csv',mime='text/csv')
