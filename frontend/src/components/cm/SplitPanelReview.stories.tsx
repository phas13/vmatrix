import type { Meta, StoryObj } from '@storybook/react'
import { Typography, Button, Box } from '@mui/material'
import SplitPanelReview from './SplitPanelReview'

const meta: Meta<typeof SplitPanelReview> = {
  title: 'Components/CM/SplitPanelReview',
  component: SplitPanelReview,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof SplitPanelReview>

export const Loading: Story = {
  args: {
    isLoading: true,
    leftContent: <></>,
    rightContent: <></>,
  },
}

export const Ready: Story = {
  args: {
    isLoading: false,
    leftContent: (
      <Box>
        <Typography variant="h6">Alice Brown — Cloud Infrastructure</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>
          This is where the session transcript would appear.
        </Typography>
      </Box>
    ),
    rightContent: (
      <Box>
        <Typography variant="caption" color="text.secondary">AI Score</Typography>
        <Typography variant="h4">72</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>
          Decision controls would appear here.
        </Typography>
      </Box>
    ),
  },
}

export const Deciding: Story = {
  args: {
    isLoading: false,
    leftContent: (
      <Box>
        <Typography variant="h6">Bob Smith — DevOps Practices</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>
          Q1 — Theoretical: What is CI/CD?
        </Typography>
        <Typography variant="body2">Response: Continuous integration and delivery pipeline.</Typography>
        <Typography variant="body2" color="text.secondary">AI Rationale: Correct but lacks depth.</Typography>
      </Box>
    ),
    rightContent: (
      <Box>
        <Typography variant="caption" color="text.secondary">AI Score</Typography>
        <Typography variant="h4">60</Typography>
        <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
          <Button variant="outlined" disabled>Uphold</Button>
          <Button variant="outlined" color="error" disabled>Override</Button>
        </Box>
      </Box>
    ),
  },
}

export const Decided: Story = {
  args: {
    isLoading: false,
    leftContent: (
      <Box>
        <Typography variant="h6">Carol White — Backend Development</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>Full transcript visible here.</Typography>
      </Box>
    ),
    rightContent: (
      <Box>
        <Typography variant="caption" color="text.secondary">AI Score</Typography>
        <Typography variant="h4">85</Typography>
        <Typography sx={{ mt: 2 }}>Decision: Upheld</Typography>
      </Box>
    ),
  },
}
