'use client';

import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  HStack,
  Icon,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Progress,
  Text,
  useColorModeValue,
  useDisclosure,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { InfoIcon, WarningIcon } from '@chakra-ui/icons';
import { apiClient, type UsageStats } from '@/lib/api';

export function UsageBar() {
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [error, setError] = useState(false);
  const [passphrase, setPassphrase] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

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

  const handleExtendLimit = async () => {
    if (!passphrase.trim()) return;

    setIsSubmitting(true);
    try {
      await apiClient.extendUsageLimit(passphrase.trim());
      toast({
        title: 'Limit extended',
        description: 'Your usage limit has been increased.',
        status: 'success',
        duration: 3000,
      });
      setPassphrase('');
      onClose();
      fetchUsage();
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Invalid passphrase';
      toast({
        title: 'Failed to extend limit',
        description: errorMessage,
        status: 'error',
        duration: 4000,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (error || !usage) {
    return null;
  }

  const usedPct = (usage.total_cost_usd / usage.limit_usd) * 100;
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
                Usage:
              </Text>
              <Text fontSize="sm" color={textColor}>
                ${usage.total_cost_usd.toFixed(4)} / ${usage.limit_usd.toFixed(2)}
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
              <Button
                size="xs"
                colorScheme="red"
                variant="ghost"
                onClick={onOpen}
              >
                Extend Limit
              </Button>
            </HStack>
          )}
        </HStack>
      </Box>

      <Modal isOpen={isOpen} onClose={onClose} size="md">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>About Usage Limits</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Box>
                <Text fontWeight="600" mb={2}>What is this?</Text>
                <Text fontSize="sm" color={mutedColor}>
                  OpenFDA Explorer uses AI to analyze FDA medical device data. Each query consumes
                  tokens from the underlying language model, which has an associated cost.
                </Text>
              </Box>

              <Box>
                <Text fontWeight="600" mb={2}>Why is there a limit?</Text>
                <Text fontSize="sm" color={mutedColor}>
                  To keep this tool free and accessible, each visitor has a usage allowance of
                  ${usage?.limit_usd.toFixed(2) || '1.50'} in API costs. This prevents abuse and
                  ensures fair access for everyone.
                </Text>
              </Box>

              <Box>
                <Text fontWeight="600" mb={2}>Your current usage</Text>
                <Text fontSize="sm" color={mutedColor}>
                  {usage?.request_count || 0} requests made<br />
                  {usage?.total_input_tokens.toLocaleString() || 0} input tokens + {usage?.total_output_tokens.toLocaleString() || 0} output tokens<br />
                  Total cost: ${usage?.total_cost_usd.toFixed(4) || '0.0000'}
                </Text>
              </Box>

              <Box borderTopWidth="1px" pt={4}>
                <Text fontWeight="600" mb={2}>Need more?</Text>
                <Text fontSize="sm" color={mutedColor} mb={3}>
                  If you have a passphrase, enter it below to extend your limit. Otherwise,
                  contact the developer to request additional quota.
                </Text>

                <FormControl>
                  <FormLabel fontSize="sm">Passphrase</FormLabel>
                  <Input
                    type="password"
                    placeholder="Enter passphrase"
                    value={passphrase}
                    onChange={(e) => setPassphrase(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && passphrase.trim()) {
                        handleExtendLimit();
                      }
                    }}
                  />
                </FormControl>
              </Box>
            </VStack>
          </ModalBody>

          <ModalFooter>
            <Button
              colorScheme="brand"
              onClick={handleExtendLimit}
              isLoading={isSubmitting}
              isDisabled={!passphrase.trim()}
            >
              Extend Limit
            </Button>
          </ModalFooter>
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
