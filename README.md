# GaetanoFallettaPersonalExpenseSystem
GESTIONE DELLE SPESE PERSONALI E DEL BUDGET
```mermaid
flowchart TD
    A[START] --> B{La base dati esiste?}

    B -- No --> C[Crea Base Dati]
    C --> D{Creazione eseguita?}
    D -- No --> C
    D -- Si --> E[Visualizzazione Menu]

    B -- Si --> E

    E --> F1[1 - Gestione Categorie]
    E --> F2[2 - Inserisci Spesa]
    E --> F3[3 - Definisci Budget]
    E --> F4[4 - Visualizza Report]
    E --> F5[5 - Esci]

    F5 --> G[END]
```
