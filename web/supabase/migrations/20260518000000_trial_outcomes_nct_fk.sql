alter table trial_outcomes
  add constraint fk_trial_outcomes_nct_id
  foreign key (nct_id) references clinical_trials(nct_id)
  not valid;
