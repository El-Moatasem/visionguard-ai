# Evidence snapshots, export and review

Feature 5 links observed potential hazards and uncertainty intervals to a human decision.
The evidence dashboard lets a reviewer save a snapshot of **the current rule** and a completed SAM
tracking job, seek to an approximate event time, and mark an item **confirmed**, **rejected**, or
**unresolved**. A reviewer can change their mind, creating a new dated review entry while retaining
previous entries. A decision does not change the original model result.

The export file contains an explicit source hash, rule definition, event/review intervals, source IDs,
selected bounding-box observations and the full review history. Printable HTML escapes user-provided
strings and uses a restrictive content-security policy. No original video frames are exported.

Use only with authorized videos and local endpoints. It does not provide authentication, formal chain
of custody or production-grade tamper resistance. Report review status is **human opinion**, not an
independent fact about whether a safety regulation has been violated.
