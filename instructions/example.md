# Example: Database Query Review

When reviewing changes that touch database queries, check for:
- N+1 query patterns
- Missing indexes on frequently filtered columns
- Raw SQL with user input (SQL injection risk)
