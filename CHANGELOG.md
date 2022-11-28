# v1.17.0 (xxxx-xx-xx)
- Replace commonmark with markdown-it and remove django-markwhat dependency
- Support python 3.10
- Update some depdencies
- Remove suggested interviewer for interview
- Add limited_to_source field to restrict access for external consultants
- Add privilege field to consultant to implement access filtering
- Update search, allowing user to search old candidate but not the detail
- Add upload a file on interview
- Add next interview goal on minute
- Add possibility to display archived sources on active-sources page

# v1.16.0 (2022-11-14)
- More refined factories
- New command: create_dev_dataset to generate a basic dev dataset
- Add process creator, creation date and linkedin url on process page
- Add view tests
- Add interview planned date in process creation
- Update more appropriate column titles for process table
- Add ordering to Consultant (remove a warning)

# v1.15.0 (2022-10-20)
- All interviews: only display active interviewers in filter dropdown
- Fix NonExistentTimeError that could happen exactly 30 or 7 days after spring DST change
- Fix character escaping in email body
- Add interview kind to all_interviews.tsv export
- Re-enable the dump_data view, which was unreachable since the django 3.2 migration
- Set default autofield type
- Update black to 22.8.0
- Security / CVE
  - Update to django 3.2.16
  - Update numpy to 1.23.4
  - Update urllib3 to 1.26.12
- Migrate from pipenv to poetry
- Support only python 3.9

# v1.14.0 (2022-03-07)
- Update django to 3.2.12
- New page: list past and future interviews
- Fix an error when we reopen a closed process wthout interview
- Show kind of interview on plan form and minute form

# v1.13.0 (2022-01-26)
- Add interview.prequalification to interviews TSV export
- Add kind of interview, will allow differentiating phone call, visio or physical interview
- Update to django 3.1.14
- Limit ics history 1 month
- Optimize table sql queries
- Add offers to processes and interviews exports
- Add a page to follow offers
- Add per offer process follow up
  - Accessible from all offers page, offers admin page, process page

# 1.12.1 (2021-11-19)
- Fix page load if interviewer don't have prequalification interviews

# 1.12.0 (2021-11-18)
- Admin:
  - Process: Filter and sort by state
- CI:
  - Run tests against mariadb
- Remove uneeded productive flag on consultant
- Use select2 form to select suggested interviewer and filter disabled users
- Stop spamming RH via email
- New ICS feeds: per subsidiary and per user
- Bugs
  - Fix source report page, show count filtered by subsidiary
- Provisionning API now uses company code instead of full name
- Add prequalification flag to interview
- Set planned date to today if not present when completing interview

# 1.11.4 (2021-10-19)
- Fix activity summary page (lazy translation)

# 1.11.3 (2021-10-19)
- Fix reverse url usage when we validate minute

# 1.11.2 (2021-10-19)
- Invert migration 16/17

# 1.11.1 (2021-10-19)
- Fix digest computation

# 1.11.0 (2021-10-15)
- Update to django 3.1.13
- Add anonymization feature and candidate duplication prevention
- Provide more meaningful urls for process and interviews 
  - Process: /process/<id>_<candidate>/
  - Interview: /interview/<id>_<candidate>_<interviewers>_<rank>/minute/ (no url regression)
- Log candidate and interview updated in Admin History
- Handle markdown for process candidate "other information" field

# 1.10.1 (2021-04-12)
- All interviews export: fix a crash when an interview didn't have a date

# 1.10.0 (2021-03-24)
- Admin:
  - Interview: filter by state and by subsidiary. Search by candidate name
  - Process: search by candidate name
  - Document: search by candidate name, filter by document type
- Fast insert mode: Allow to create first interview when you create a new process
- Update to django 3.1.7

# 1.9.0 (2021-02-17)
- Update to django 3

# 1.8.0 (2021-02-17)
- Preselect the current consultant company in the new process form
- Replace Monthly summary with a date range summary
- Add a bar chart of interviews state over time to the summary page

# 1.7.1 (2020-12-01)
- Monthly summary:
  - Distinct and count active sources
  - Make dates timezones aware

# 1.7.0 (2020-12-01)
- Add Api for account creation and delete
- Update django-filter to 2.4.0
- Redirect to candidate's page upon creation
- Add monthly summary page

# 1.6.0 (2020-07-09)
- Add gantt diagram to show contract start date
- Add list of active sources
- Update django to last patch version (2.2.13)

# 1.5.0 (2020-05-28)
- Speed up interviews export
- Add processes export
- Dev dependencies updates (debug toolbar)

# 1.4.0 (2020-05-14)
- Add a page listing processes for a given source

# 1.3.0 (2020-02-24)
- Add sources to process admin
- Sort sources by name

# 1.2.0 (2020-01-09)
- Add state when a candidate was contacted and we wait his feedback for interview planning
- Add view to import seekube ics file. Need to add a settings to your local.py file SEEKUBE_SOURCE_ID parameter
- Add other information field to a process
- Add offer to process

# 1.1.1 (2019-09-09)
Fix python 3.5 support

# 1.1.0 (2019-09-09)
- Rework interview table
- Minute page use read mode even for interviewer when minute exist. Redirect to read mode after editing (allow user to correct malformatted markdown)  
- Update to django 2.2.5
- Fix coding style pep8
- Use black to enforce coding style
- Migrate from requirements.txt to Pipfile
- Use django-split-settings
- Add search capabilities

# 1.0.5 (2019-06-24)
Fix plan datepicker

# 1.0.4 (2019-06-17)
Fix interview form

# 1.0.3 (2019-06-14)
Fix key error on table rendering

# 1.0.2 (2019-06-13)
Fix python 3.5 support

# 1.0.1 (2019-06-13)
Add missing migration

# 1.0.0 (2019-06-13)
First official release


