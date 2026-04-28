import { Typography } from '@mui/material';

export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <Typography variant="h1" sx={{ p: 4 }}>
      {title}
    </Typography>
  );
}
