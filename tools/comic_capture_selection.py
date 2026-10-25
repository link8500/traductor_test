"""Select complete overlapping OCR captures without consulting expected words."""
import collections

def area(row):
    a,b,c,d=row['bounds'];return max(0,c-a)*max(0,d-b)

def overlaps(first,second):
    a,b,c,d=first['bounds'];e,f,g,h=second['bounds']
    return max(0,min(c,g)-max(a,e))*max(0,min(d,h)-max(b,f))>.7*min(area(first),area(second))

def prefer(new,old):
    new_area,old_area=area(new),area(old)
    new_letters=sum(c.isalpha() for c in new['source']);old_letters=sum(c.isalpha() for c in old['source'])
    # A partial paragraph inside a complete one must not suppress its remainder.
    if new_area>old_area*1.15 and new_letters>=old_letters*.8:return True
    if old_area>new_area*1.15 and old_letters>=new_letters*.8:return False
    return new['capture_edge_clearance']>old['capture_edge_clearance']

def select_captures(rows):
    selected=collections.defaultdict(list)
    for row in rows:
        assert 'capture_edge_clearance' in row,'Requires the native all-candidates capture path'
        candidates=selected[row['image']]
        matches=[i for i,old in enumerate(candidates) if overlaps(row,old)]
        if matches and not all(prefer(row,candidates[i]) for i in matches):continue
        for index in reversed(matches):candidates.pop(index)
        candidates.append(row)
    return [row for image in sorted(selected) for row in sorted(selected[image],key=lambda r:(r['bounds'][1],r['bounds'][0]))]
