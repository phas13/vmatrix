import '@testing-library/jest-dom';
import { configureAxe } from 'jest-axe';

configureAxe({ rules: { region: { enabled: false } } });
