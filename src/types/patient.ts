export type PatientData = {
  age: string;
  ageYears: string;

  sex: string;
  sexLabel: string;

  pregnancyStatus: string;
  pregnancyStatusLabel: string;

  race: string;
  raceLabel: string;

  educationLevel: string;
  educationLevelLabel: string;

  occupationCode: string;
  occupationName: string;

  residenceState: string;
  residenceStateLabel: string;
  residenceMunicipality: string;
  residenceHealthRegion: string;

  diseaseCode: string;

  notificationDate: string;
  notificationYear: string;
  notificationMonth: string;
  notificationDay: string;
  notificationEpiWeek: string;

  notifMunicipality: string;
  notifHealthRegion: string;
  healthFacility: string;

  symptomOnsetDate: string;
  daysToNotification: string;
  symptomEpiYear: string;
  symptomEpiWeekNumber: string;

  hospitalized: string;
  hospitalState: string;
  hospitalStateLabel: string;
};