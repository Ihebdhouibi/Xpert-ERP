# System Context (C4 Level 1)

```mermaid
flowchart LR
    subgraph Users
        Admin[Admin or Manager]
        Sec[Secretary or Reception]
        Mech[Mechanic on tablet]
        Acct[Accountant]
        Cust[Customer<br/>via signed link only]
    end

    subgraph External[External Systems]
        Mail[Email provider SMTP]
        SMS[SMS gateway]
        Pay[Payment terminal TPE]
        Acc[Accounting software]
        Obj[Object storage S3 compatible]
        Backup[Cloud backup target]
    end

    GMS[Xpert-ERP GMS Web Application]

    Admin --> GMS
    Sec --> GMS
    Mech --> GMS
    Acct --> GMS
    Cust -. quote approval .-> GMS

    GMS --> Mail
    GMS --> SMS
    GMS --> Obj
    GMS --> Backup
    GMS -. export .-> Acc
    Pay -. recorded by hand or future integration .-> GMS
```

The customer is not a logged-in user of the system. They interact with Xpert-ERP only via single-use signed links sent in notifications (quotation approval, optional receipt or status link). All other actors are authenticated and bound to a `garage_id` via their role.
