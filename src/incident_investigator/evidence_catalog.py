"""Extractive source catalog: the model selects references, never authors quotations."""
import json
import re
from pydantic import BaseModel, ConfigDict, Field


class StrictSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class EvidenceSelection(StrictSelection):
    sufficient: bool
    supporting_fact_ids: list[str] = Field(max_length=12)


class ReportSelection(StrictSelection):
    finding_ids: list[str] = Field(min_length=1, max_length=20)
    hypothesis_fact_ids: list[str] = Field(max_length=3)
    # User-visible limitations are supplied locally, not unconstrained factual prose.


def _spans(row):
    text = row['chunk_text']
    if row['source_type'] == 'synthetic':
        # Preserve the authoritative labeled values, not repeated narrative paraphrases.
        for key, kind in [('root_cause','root_cause'),('resolution','resolution'),('symptoms','observation')]:
            match = re.search(r'^'+key+r': (.+)$',text,re.M)
            if match and match.group(1).strip().lower() not in {'null','none','unknown','not documented'}:
                yield kind,match.start(1),match.end(1),'labeled_'+key
        return
    # Split source prose into complete local sentence spans; never create/rewrite text.
    candidates=[]
    for match in re.finditer(r'[^\n]+',text):
        line=match.group()
        if line.lstrip().startswith(('#','|','* Share:')): continue
        for sentence in re.finditer(r'.+?(?:[.!?](?=\s|$)|$)',line):
            value=sentence.group().strip()
            if len(value)<35 or len(value)>900: continue
            start=match.start()+sentence.start()+len(sentence.group())-len(sentence.group().lstrip())
            end=start+len(value)
            # Markers rank excerpts for salience, never establish their causal role.
            # Public prose has no trusted field labels: do not promote background
            # or prevention sentences into historical incident causes/resolutions.
            marker=re.search(r'\b(because|due to|caused|causing|led to|resulted in|restored|resolving|resolved|reloaded|rolled back)\b',value,re.I)
            candidates.append(('observation',start,end,'public_marker' if marker else 'public_observation'))
    preferred=candidates[:3]+[c for c in candidates if c[3]=='public_marker']+candidates
    seen=set()
    for candidate in preferred:
        if candidate[1:] not in seen:
            seen.add(candidate[1:]);yield candidate
            if len(seen)>=16: break


def build_catalog(evidence, char_budget=17000):
    groups=[]
    for row in evidence:
        entries=[]
        for kind,start,end,basis in _spans(row):
            entries.append({'chunk_id':row['id'],'incident_id':row['incident_id'],'title':row['title'],'source_type':row['source_type'],'kind':kind,'quote':row['chunk_text'][start:end],
                            'start':start,'end':end,'basis':basis})
        groups.append(entries)
    catalog=[]
    # Round robin avoids consuming the entire prompt budget on one public report.
    for index in range(max(map(len,groups),default=0)):
        for entries in groups:
            if index>=len(entries): continue
            entry={'fact_id':f'F{len(catalog)+1:03d}',**entries[index]}
            if len(json.dumps(catalog+[entry]))<=char_budget: catalog.append(entry)
    return catalog


def validate_catalog(catalog,evidence):
    rows={row['id']:row for row in evidence};errors=[];seen=set()
    for fact in catalog:
        row=rows.get(fact['chunk_id'])
        if fact['fact_id'] in seen: errors.append('Duplicate catalog fact ID.')
        seen.add(fact['fact_id'])
        if row is None or row['chunk_text'][fact['start']:fact['end']]!=fact['quote']:
            errors.append('Source span/quotation mismatch: '+fact['fact_id']);continue
        if any(fact.get(key)!=row.get(key) for key in ('incident_id','title','source_type')):
            errors.append('Source identity mismatch: '+fact['fact_id'])
        if row['source_type']=='synthetic':
            key={'root_cause':'root_cause','resolution':'resolution','observation':'symptoms'}.get(fact['kind'])
            if not key or not re.search(r'^'+key+': '+re.escape(fact['quote'])+r'$',row['chunk_text'],re.M):
                errors.append('Historical field interpretation disagrees with source: '+fact['fact_id'])
        elif not any((kind,start,end)==(fact['kind'],fact['start'],fact['end']) for kind,start,end,_ in _spans(row)):
            errors.append('Public source interpretation disagrees with extraction rules: '+fact['fact_id'])
    return errors


def resolve_selection(selection,catalog,evidence):
    """Reject bad IDs or relationships; never silently discard an invalid selection."""
    errors=validate_catalog(catalog,evidence);facts={f['fact_id']:f for f in catalog}
    selected=list(dict.fromkeys(selection.finding_ids));hypotheses=list(dict.fromkeys(selection.hypothesis_fact_ids))
    if any(identifier not in facts for identifier in selected+hypotheses):
        return [],[],errors+['Selected evidence ID does not belong to retrieved source catalog.']
    if any(identifier not in selected or facts[identifier]['kind']!='root_cause' for identifier in hypotheses):
        errors.append('Hypothesis must reference a selected validated root-cause fact.')
    # Restore documented synthetic field pairs before the unchanged quote/citation gate.
    selected_chunks={facts[identifier]['chunk_id'] for identifier in selected}
    synthetic={r['id'] for r in evidence if r['source_type']=='synthetic'}
    for fact in catalog:
        if fact['chunk_id'] in selected_chunks & synthetic and fact['kind'] in {'root_cause','resolution'} and fact['fact_id'] not in selected:
            selected.append(fact['fact_id'])
    return [facts[i] for i in selected],[facts[i] for i in hypotheses],errors


def render_hypothesis(fact):
    # No free-form generated interpretation can swap an actor or reverse negation.
    text='Investigate whether this documented historical mechanism also applies to the current incident: '+fact['quote']
    return {'hypothesis':text,'supporting_chunk_ids':[fact['chunk_id']],
            'diagnostic_checks':['Compare current logs, configuration changes, and telemetry with the quoted historical mechanism before accepting or ruling it out.']}


def validate_mechanisms(hypotheses, facts):
    """An extractive interpretation cannot reverse an actor or negate its source."""
    if len(hypotheses) != len(facts):
        return ['Hypothesis/source mechanism count mismatch.']
    errors=[]
    for hypothesis,fact in zip(hypotheses,facts):
        expected='Investigate whether this documented historical mechanism also applies to the current incident: '+fact['quote']
        if hypothesis.hypothesis != expected or hypothesis.supporting_chunk_ids != [fact['chunk_id']]:
            errors.append('Hypothesis interpretation differs from its exact documented mechanism.')
    return errors
