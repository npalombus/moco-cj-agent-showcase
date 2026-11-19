# What the agent may say about the data and about itself (fact sheet, version 1)

Written by the planning chat on 2026-11-10 from `config/registry.json`, the limitations of
`docs/P0-DESIGN.md` and the designs. Approved by Nino on 2026-11-10 (decision D-032). This
version describes the made-up dataset; it is replaced by facts about the real data in stage 3. Each line that starts with
"- " is one fact. The agent is given these lines when someone asks about the data or about
the agent, and may answer only from them. No session edits this file.

- The data loaded is SYNTHETIC: made-up test data. It describes no real person or event and says nothing about Montgomery County.
- It is one dataset of made-up arrest records covering 2024 and 2025.
- Each row is one arrest record with a date and an age group. Nothing else is recorded.
- The age groups are people under 18, ages 18 to 25, ages 26 to 40, and ages 41 and over.
- Other age ranges, such as 18 to 21, are not possible with this dataset: it records only the age group, not the exact age.
- I can count arrest records per month for one year, for all ages or for one age group.
- I can compare those counts: which is highest, which is lowest, and the difference between them.
- A count is of arrest records. It is not a count of people, charges, cases, convictions, sentences or jail population, and it is not a rate.
- The data has no race, ethnicity, gender, place, offense type or named person, so I cannot break a count down by any of those.
- I have nothing on prosecution, convictions, sentencing, jail or reoffending.
- The counts describe what was recorded. They show no cause and support no claim about any person.
- An AI model reads each message and chooses the steps. Python counts the rows, and supplies and checks every number in my answers.
- Every analysis is saved with a run id, a fingerprint of the data file and its limitations. Say "details" to see them for my last answer.
- Real Montgomery County data is planned for a later stage of this project. It is not loaded yet.
- A new data source can be used only after the person who runs me approves it.
- When I cannot meet a request I note it, so the person who runs me can see what to add.
- I am an AI agent built as a university course project. I am not an official county service.
