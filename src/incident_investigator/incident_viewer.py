"""Read-only lookup of original incident records inside the approved dataset.

Citation paths and user-supplied IDs are never used to construct a file path.
The existing source records form the local lookup manifest. Partial public
records can be displayed without pretending a full article is available.
"""
import json
import re
from .ingestion import ROOT


class IncidentUnavailable(ValueError):
    pass


def load_incident(incident_id, source_type):
    """Resolve an identity through approved, non-symlink source records only."""
    if source_type not in {'synthetic', 'public'} or not isinstance(incident_id, str):
        raise IncidentUnavailable('This incident has no supported local source record.')
    pattern = r'SYN-\d{3}' if source_type == 'synthetic' else r'PUB-[0-9a-f]{12}'
    if not re.fullmatch(pattern, incident_id):
        raise IncidentUnavailable('This incident has no supported local source record.')
    base = ROOT / 'data' / 'incidents'
    folder = base / source_type
    # Reject symlinks in every dataset path component, including directory links.
    if any(p.is_symlink() for p in (ROOT / 'data', base, folder)):
        raise IncidentUnavailable('The local incident source could not be opened safely.')
    approved = folder.resolve()
    for candidate in sorted(folder.glob('*.json')):
        # Filename is obtained from the dataset inventory, never from the ID.
        if candidate.stem != incident_id:
            continue
        try:
            if candidate.is_symlink() or candidate.resolve().parent != approved:
                raise ValueError('Outside approved dataset')
            if candidate.stat().st_size > 2_000_000:
                raise ValueError('Oversized source record')
            record = json.loads(candidate.read_text(encoding='utf-8'))
            if not isinstance(record, dict) or record.get('incident_id') != incident_id or record.get('source_type') != source_type:
                raise ValueError('Source identity mismatch')
            if not isinstance(record.get('title'), str) or not record['title'].strip():
                raise ValueError('Missing source title')
            return record
        except (OSError, ValueError, UnicodeError):
            raise IncidentUnavailable('The local incident report is unreadable or invalid. Its cited passages remain available below.') from None
    raise IncidentUnavailable('The original incident report is not available in this local dataset. Its cited passages remain available below.')


def group_incidents(report):
    """Group accepted findings without modifying generated content or citations."""
    if report.get('status') != 'investigation':
        return []
    groups = {}
    for row in report.get('similar_historical_incidents', []):
        identifier = row.get('incident_id')
        if identifier:
            groups.setdefault(identifier, {'source': row, 'findings': []})
    for heading, field in [('Historical root causes', 'historical_root_causes'),
                           ('Documented historical resolutions', 'previous_resolutions'),
                           ('Historical observations', 'historical_observations')]:
        for row in report.get(field, []):
            identifier = row.get('incident_id')
            if identifier:
                group = groups.setdefault(identifier, {'source': row, 'findings': []})
                group['findings'].append((heading, row))
    return list(groups.values())
