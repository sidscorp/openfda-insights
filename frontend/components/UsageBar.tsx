'use client';

import { useEffect, useState } from 'react';
import {
  Box,
  HStack,
  Icon,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalHeader,
  ModalOverlay,
  Progress,
  Text,
  useColorModeValue,
  useDisclosure,
  VStack,
} from '@chakra-ui/react';
import { InfoIcon, WarningIcon } from '@chakra-ui/icons';
import { apiClient, type UsageStats } from '@/lib/api';

export function UsageBar() {
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [error, setError] = useState(false);
  const { isOpen, onOpen, onClose } = useDisclosure();

  const bg = useColorModeValue('gray.100', 'gray.900');
  const textColor = useColorModeValue('gray.600', 'gray.300');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');

  const fetchUsage = async () => {
    try {
      const stats = await apiClient.getUsage();
      setUsage(stats);
      setError(false);
    } catch (err) {
      console.error('Failed to fetch usage:', err);
      setError(true);
    }
  };

  useEffect(() => {
    fetchUsage();
    const interval = setInterval(fetchUsage, 30000);
    return () => clearInterval(interval);
  }, []);

  if (error || !usage) {
    return null;
  }

  const usedPct = (usage.request_count / usage.request_limit) * 100;
  const isWarning = usedPct >= 50 && usedPct < 80;
  const isDanger = usedPct >= 80;

  const colorScheme = isDanger ? 'red' : isWarning ? 'yellow' : 'green';

  return (
    <>
      <Box bg={bg} px={4} py={2} borderTopWidth="1px" borderColor={useColorModeValue('gray.200', 'gray.700')}>
        <HStack justify="space-between" align="center">
          <HStack spacing={4} flex="1">
            <HStack spacing={2}>
              <Text fontSize="sm" fontWeight="500" color={textColor}>
                Requests:
              </Text>
              <Text fontSize="sm" color={textColor}>
                {usage.request_count} / {usage.request_limit}
              </Text>
              <Icon
                as={InfoIcon}
                boxSize={3}
                color={mutedColor}
                cursor="pointer"
                onClick={onOpen}
                _hover={{ color: 'brand.500' }}
              />
            </HStack>

            <Box flex="1" maxW="200px">
              <Progress
                value={Math.min(usedPct, 100)}
                size="xs"
                colorScheme={colorScheme}
                borderRadius="full"
              />
            </Box>
          </HStack>

          {isDanger && (
            <HStack spacing={2}>
              <WarningIcon color="red.500" />
              <Text fontSize="xs" color="red.500" fontWeight="500">
                Limit reached
              </Text>
            </HStack>
          )}
        </HStack>
      </Box>

      <Modal isOpen={isOpen} onClose={onClose} size="md">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>About Usage Limits</ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            <VStack spacing={4} align="stretch">
              <Box>
                <Text fontWeight="600" mb={2}>What is this?</Text>
                <Text fontSize="sm" color={mutedColor}>
                  OpenFDA Explorer uses AI to analyze FDA medical device data. Each query
                  uses a free AI model via OpenRouter.
                </Text>
              </Box>

              <Box>
                <Text fontWeight="600" mb={2}>Why is there a limit?</Text>
                <Text fontSize="sm" color={mutedColor}>
                  To keep this tool accessible, each visitor has an allowance of
                  {' '}{usage?.request_limit || 100} requests. This prevents abuse and
                  ensures fair access for everyone.
                </Text>
              </Box>

              <Box>
                <Text fontWeight="600" mb={2}>Your current usage</Text>
                <Text fontSize="sm" color={mutedColor}>
                  {usage?.request_count || 0} / {usage?.request_limit || 100} requests used<br />
                  {usage?.requests_remaining || 0} requests remaining<br />
                  {usage?.total_input_tokens.toLocaleString() || 0} input + {usage?.total_output_tokens.toLocaleString() || 0} output tokens
                </Text>
              </Box>
            </VStack>
          </ModalBody>
        </ModalContent>
      </Modal>
    </>
  );
}

export function useUsageRefresh() {
  const [refreshKey, setRefreshKey] = useState(0);

  const triggerRefresh = () => {
    setRefreshKey((prev) => prev + 1);
    window.dispatchEvent(new CustomEvent('usage-refresh'));
  };

  return { triggerRefresh };
}
