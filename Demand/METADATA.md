# Data sources

- BISA - Brussels Institute for Statistics and Analysis
  - Load Macrozones to get the pentagone boundaries
  
- UrbIS (Vector product) - Paradigm (CIRB-CIBG-BRIC)
  - Load Parcels and buildings
  - Load Administrative units
  - Load Transport networks

- BruGIS - Urban.brussels
  - Load Heritage
  - Load Legal inventory
  - Load segments and nodes

- OSM - OpenStreetMap
  - Load building footprints
  - Load street network

- SitEx - Perspective.brussels
  - Load building types
  - Load floor areas

- Zonal Vision - Brussels Environment
  - Load access to resources
  
# Heritage and Legal inventory (CoBAT)

The Brussels Town Planning Code (CoBAT - Code Bruxellois de l'Aménagement du Territoire) establishes rules to protect buildings listed in the legal inventory.

- Art. 206 - Immovable heritage
  - Monument = Any particularly remarkable structure, including installations or decorative features forming an integral part of that structure.
  - Complex = Any group of immovable properties forming an urban or rural complex that is sufficiently coherent to be defined topographically and is notable for its homogeneity or its integration into the landscape.
  - Site = Any work of nature or of man, or any combined work of man and nature, constituting a space that is unbuilt or partially built and which exhibits spatial coherence.

- Art. 207
  - Any application for a permit relating to a property listed in the legal inventory is subject to the opinion of the consultation committee. The Royal Commision for Monuments and Sites (CRMS) is consulted only at the request of the consulation committe.
  - The Government may exempt the requiremnt for prior notification to the consultation committee.

## Legal inventory

Planning application relating to any properties (buildings) included in the inventory requires the opinion to the consultation committee that may decide to request consultation from the Royal Commision for Monuments and Sites (CRMS). The government still may exempt this requirement.

## Register of protected Heritage

Some properties in the legal inventory are subjected to stricter protection measures.

### Preservation list ('protected')

- Art. 214
  - The owner of a property listed on the preservation list is obliged to maintain it in good condition and to comply with any specific conservation requirements that may have been imposed. 
  
- Art. 216
  - A property listed on the preservation list is automatically included in the inventory of built heritage.

> In BruGIS:
> - AG1: Decree in progress
> - AG2: Final decree

### Classificiation ('registered')

- Art. 231
  - Same as Art. 214, 217 and 218.

- Art. 232
  - It is prohibited to:
    - Demolish, in whole or in part, a property forming part of the listed built heritage;
    - Use such a property or to alter its use in such a way that it loses its significance in accordance with the criteria set out in Art. 206;
    - Carry out works on such a property in breach of the specific conservation conditions;
    - Move, in whole or in part, a property forming part of the listed built heritage, unless the physical preservation of the property absolutely requires it and provided that the necessary safeguards for its dismantling, transfer and reassembly in a suitable location are put in place. 

- Art. 235
  - A classified property is automatically included in the inventory of listed heritage.

> In BruGIS:
> - AG1: Decree in progress
> - AG2: Final decree
> - One shot: Automatic final decree