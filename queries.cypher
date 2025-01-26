MATCH (n)-[r]-(connected)
WHERE n:State
RETURN n, r, connected
LIMIT 10000;


MATCH (n)-[r]-(connected)
WHERE n:Endtime OR n:Starttime
RETURN n, r, connected
LIMIT 10000;
