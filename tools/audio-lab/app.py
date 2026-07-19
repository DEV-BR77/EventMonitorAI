from __future__ import annotations
import io, tempfile
from datetime import datetime
from pathlib import Path
import pandas as pd
import soundfile as sf
import streamlit as st
from eventmonitor.db import connect
from eventmonitor.importer import import_package, import_folder

st.set_page_config(page_title='EventMonitor AudioLab', page_icon='🎧', layout='wide')
DB=Path('data/eventmonitor.sqlite3'); LIB=Path('data/library')
LABELS=['Schreien','Rufen','Streit / mehrere Stimmen','Schlagen / Aufprall','Türknallen','Auto / Vorbeifahrt','Motorrad','Hupe','Normales Sprechen','Hund','Musik','Maschine','Wind / Regen','Hintergrund','Unklar']
conn=connect(DB)
page=st.sidebar.radio('Bereich',['Übersicht','Import','Ereignisse lernen','Auswertung'])

if page=='Import':
    st.title('Messungen importieren')
    uploads=st.file_uploader('ZIP-Dateien auswählen',type=['zip'],accept_multiple_files=True)
    if st.button('Ausgewählte Dateien importieren',type='primary',disabled=not uploads):
        for u in uploads:
            with tempfile.NamedTemporaryFile(delete=False,suffix='.zip') as t: t.write(u.getbuffer()); tmp=Path(t.name)
            try:
                rid,created=import_package(tmp,DB,LIB); st.success(f'{u.name}: Aufnahme #{rid} – '+('importiert' if created else 'bereits vorhanden'))
            except Exception as e: st.error(f'{u.name}: {e}')
            finally: tmp.unlink(missing_ok=True)
    folder=st.text_input('Oder vorhandenen Ordner rekursiv importieren')
    if st.button('Ordner importieren',disabled=not folder):
        rows=import_folder(folder,DB,LIB); st.dataframe(pd.DataFrame(rows,columns=['Datei','Aufnahme','Status','Fehler']),use_container_width=True)

elif page=='Übersicht':
    st.title('EventMonitor AudioLab – Übersicht')
    recs=pd.read_sql_query('SELECT * FROM recordings ORDER BY started_at DESC',conn)
    segs=pd.read_sql_query('SELECT * FROM segments',conn)
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Aufnahmen',len(recs)); c2.metric('Audiostunden',f"{recs.duration_seconds.sum()/3600:.1f}" if len(recs) else '0')
    c3.metric('Segmente',len(segs)); c4.metric('Bestätigt',int(segs.label.notna().sum()) if len(segs) else 0)
    if len(recs): st.dataframe(recs[['id','started_at','duration_seconds','sample_rate','channels','source_path']],use_container_width=True)
    else: st.info('Noch keine Messungen importiert.')

elif page=='Ereignisse lernen':
    st.title('Ereignisse anhören und zuordnen')
    recs=conn.execute('SELECT * FROM recordings ORDER BY started_at DESC').fetchall()
    if not recs: st.info('Zuerst Messungen importieren.'); st.stop()
    rec_map={f"#{r['id']} | {r['started_at']} | {Path(r['audio_path']).name}":r for r in recs}
    rec=rec_map[st.selectbox('Aufnahme',list(rec_map))]
    only_open=st.checkbox('Nur unbestätigte Segmente',True)
    order=st.selectbox('Reihenfolge',['Auffälligste zuerst','Lauteste zuerst','Chronologisch'])
    order_sql={'Auffälligste zuerst':'event_score DESC','Lauteste zuerst':'peak_dba DESC','Chronologisch':'start_seconds'}[order]
    sql='SELECT * FROM segments WHERE recording_id=?'+(' AND label IS NULL' if only_open else '')+f' ORDER BY {order_sql}'
    segments=conn.execute(sql,(rec['id'],)).fetchall()
    if not segments: st.success('Für diese Auswahl sind keine Segmente offen.'); st.stop()
    pos=st.number_input('Position',0,len(segments)-1,0,1); seg=segments[int(pos)]
    before=st.slider('Vorlauf / Nachlauf in Sekunden',0.0,5.0,2.0,0.5)
    data,sr=sf.read(rec['audio_path'],always_2d=True)
    a=max(0,int((seg['start_seconds']-before)*sr)); b=min(len(data),int((seg['end_seconds']+before)*sr))
    buf=io.BytesIO(); sf.write(buf,data[a:b],sr,format='WAV',subtype='PCM_16')
    st.audio(buf.getvalue(),format='audio/wav')
    st.write(f"**Zeit:** {seg['start_seconds']:.1f}–{seg['end_seconds']:.1f}s · **Peak:** {seg['peak_dba']:.1f} dB(A) · **Mittel:** {seg['mean_dba']:.1f} dB(A) · **Auffälligkeit:** {seg['event_score']:.1f}")
    label=st.selectbox('Lärmart',LABELS,index=LABELS.index(seg['label']) if seg['label'] in LABELS else 0)
    confidence=st.slider('Sicherheit',0.0,1.0,float(seg['label_confidence'] or 1.0),0.05)
    notes=st.text_input('Notiz',seg['notes'] or '')
    if st.button('Bestätigen und speichern',type='primary'):
        conn.execute('UPDATE segments SET label=?,label_confidence=?,notes=?,labelled_at=? WHERE id=?',(label,confidence,notes,datetime.now().isoformat(),seg['id']))
        conn.commit(); st.success('Gespeichert. Wechsel zur nächsten Position oder Seite neu laden.')

else:
    st.title('Auswertung')
    df=pd.read_sql_query("""SELECT r.started_at,s.start_seconds,s.end_seconds,s.peak_dba,s.mean_dba,s.label,s.label_confidence,s.notes
    FROM segments s JOIN recordings r ON r.id=s.recording_id WHERE s.label IS NOT NULL ORDER BY r.started_at,s.start_seconds""",conn)
    if df.empty: st.info('Noch keine bestätigten Ereignisse.'); st.stop()
    st.bar_chart(df['label'].value_counts())
    labels=st.multiselect('Klassen filtern',sorted(df.label.unique()),default=sorted(df.label.unique()))
    out=df[df.label.isin(labels)].copy(); st.dataframe(out,use_container_width=True)
    st.download_button('Lärmprotokoll als CSV herunterladen',out.to_csv(index=False).encode('utf-8-sig'),'laermprotokoll.csv','text/csv')
