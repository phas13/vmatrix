import { Box, Button, Typography } from '@mui/material'
import { useNavigate, useParams } from 'react-router-dom'

export default function CMReviewPlaceholderPage() {
  const { type, id } = useParams()
  const navigate = useNavigate()
  return (
    <Box sx={{ p: 4 }}>
      <Typography variant="h6">Review: {type} / {id}</Typography>
      <Typography color="text.secondary" sx={{ mt: 1 }}>
        Review screen coming in the next story.
      </Typography>
      <Button sx={{ mt: 2 }} onClick={() => navigate('/cm/dashboard')}>
        Back to Dashboard
      </Button>
    </Box>
  )
}
