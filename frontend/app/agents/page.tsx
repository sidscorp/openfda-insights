'use client';

import { useState, useRef } from 'react';
import {
  Box,
  Container,
  VStack,
  Heading,
  Text,
  Input,
  Button,
  HStack,
  InputGroup,
  InputRightElement,
  Card,
  CardHeader,
  CardBody,
  SimpleGrid,
  Tag,
  Alert,
  AlertIcon,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  List,
  ListItem,
  ListIcon,
  Code,
  Divider,
  useColorModeValue,
  Badge,
} from '@chakra-ui/react';
import { SearchIcon, WarningIcon, CheckCircleIcon, TimeIcon, ChevronRightIcon } from '@chakra-ui/icons';
import EnhancedAgentProgress from '@/components/EnhancedAgentProgress';
import { apiClient, MultiAgentResult } from '@/lib/api';

export default function MultiAgentDashboard() {
  const [query, setQuery] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [results, setResults] = useState<MultiAgentResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Dynamic colors for "Google-like" professional aesthetic
  const bgGradient = useColorModeValue(
    'linear(to-b, brand.50, white)',
    'linear(to-b, gray.900, gray.800)'
  );
  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.100', 'gray.700');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isAnalyzing) return;

    setIsAnalyzing(true);
    setError(null);
    setResults(null);
  };

  const handleComplete = (result: MultiAgentResult) => {
    setResults(result);
    setIsAnalyzing(false);
  };

  const handleError = (errorMessage: string) => {
    setError(errorMessage);
    setIsAnalyzing(false);
  };

  const handleCancel = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsAnalyzing(false);
  };

  return (
    <Box minH="100vh" bg={bgGradient}>
      <Container maxW="container.xl" py={12}>
        <VStack spacing={8} align="stretch">
          {/* Header Section */}
          <VStack spacing={3} textAlign="center" mb={8}>
            <Heading
              as="h1"
              size="2xl"
              bgGradient="linear(to-r, brand.600, brand.400)"
              bgClip="text"
              letterSpacing="tight"
            >
              FDA Multi-Agent Intelligence
            </Heading>
            <Text fontSize="xl" color={mutedColor} maxW="2xl">
              Harness the power of specialized AI agents to analyze medical device data with precision and speed.
            </Text>
          </VStack>

          {/* Search Section */}
          <Box maxW="800px" mx="auto" w="full" as="form" onSubmit={handleSubmit}>
            <VStack spacing={4}>
              <InputGroup size="lg">
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Enter device name, manufacturer, or concern..."
                  bg={cardBg}
                  boxShadow="lg"
                  border="1px solid"
                  borderColor="transparent"
                  _focus={{
                    borderColor: 'brand.500',
                    boxShadow: '0 0 0 1px #3182ce',
                  }}
                  disabled={isAnalyzing}
                  fontSize="md"
                  h="16"
                  pl={6}
                />
                <InputRightElement w="auto" h="full" p={2}>
                  {!isAnalyzing ? (
                    <Button
                      type="submit"
                      colorScheme="brand"
                      size="lg"
                      h="full"
                      px={8}
                      borderRadius="lg"
                      isDisabled={!query.trim()}
                      leftIcon={<SearchIcon />}
                    >
                      Analyze
                    </Button>
                  ) : (
                    <Button
                      onClick={handleCancel}
                      colorScheme="red"
                      variant="ghost"
                      size="lg"
                      h="full"
                      px={6}
                    >
                      Cancel
                    </Button>
                  )}
                </InputRightElement>
              </InputGroup>

              <HStack spacing={3} wrap="wrap" justify="center">
                <Text fontSize="sm" color={mutedColor} fontWeight="medium">
                  Try:
                </Text>
                {['3M masks', 'insulin pumps', 'Medtronic pacemakers'].map((example) => (
                  <Button
                    key={example}
                    variant="outline"
                    size="sm"
                    colorScheme="gray"
                    onClick={() => setQuery(example)}
                    fontWeight="normal"
                    borderRadius="full"
                  >
                    {example}
                  </Button>
                ))}
              </HStack>
            </VStack>
          </Box>

          {/* Error Alert */}
          {error && (
            <Alert status="error" borderRadius="md" maxW="800px" mx="auto">
              <AlertIcon />
              {error}
            </Alert>
          )}

          {/* Analysis & Results Area */}
          {(isAnalyzing || results) && (
            <VStack spacing={8} w="full">
              {/* Progress Visualization */}
              {isAnalyzing && (
                <Box w="full" bg={cardBg} p={8} borderRadius="2xl" boxShadow="sm" border="1px" borderColor={borderColor}>
                  <EnhancedAgentProgress
                    query={query}
                    isActive={isAnalyzing}
                    onComplete={handleComplete}
                    onError={handleError}
                  />
                </Box>
              )}

              {/* Final Results */}
              {results && !isAnalyzing && (
                <VStack spacing={8} w="full" animation="fade-in 0.5s">
                  
                  {/* Intent & Summary Card */}
                  <Card w="full" variant="outline" borderColor="brand.200" bg="brand.50">
                    <CardBody>
                      <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
                        <Box>
                          <Text fontSize="xs" color="brand.600" textTransform="uppercase" fontWeight="bold">
                            Primary Intent
                          </Text>
                          <Heading size="md" mt={1}>{results.intent.primary_intent}</Heading>
                        </Box>
                        <Box>
                          <Text fontSize="xs" color="brand.600" textTransform="uppercase" fontWeight="bold">
                            Target Devices
                          </Text>
                          <HStack mt={2} wrap="wrap">
                            {results.intent.device_names.length > 0 ? (
                              results.intent.device_names.map((d, i) => (
                                <Tag key={i} colorScheme="blue" variant="solid">{d}</Tag>
                              ))
                            ) : (
                              <Text>N/A</Text>
                            )}
                          </HStack>
                        </Box>
                        <Box>
                          <Text fontSize="xs" color="brand.600" textTransform="uppercase" fontWeight="bold">
                            Agents Deployed
                          </Text>
                          <HStack mt={2}>
                            {results.intent.required_agents.map((agent, i) => (
                              <Badge key={i} colorScheme="purple">{agent}</Badge>
                            ))}
                          </HStack>
                        </Box>
                      </SimpleGrid>
                    </CardBody>
                  </Card>

                  {/* Agent Findings Grid */}
                  <SimpleGrid columns={{ base: 1, lg: 3 }} spacing={6} w="full" alignItems="start">
                    {Object.entries(results.agent_results).map(([agentName, agentData]) => {
                      const data = agentData[0];
                      if (!data || !data.key_findings) return null;

                      return (
                        <Card
                          key={agentName}
                          h="full"
                          _hover={{ transform: 'translateY(-4px)', shadow: 'xl' }}
                          transition="all 0.2s"
                        >
                          <CardHeader pb={2}>
                            <HStack justify="space-between">
                              <Heading size="md" textTransform="capitalize">
                                {agentName.replace('_', ' ')}
                              </Heading>
                              <Badge colorScheme={agentName === 'analyzer' ? 'orange' : 'teal'}>
                                {data.data_points || 0} Records
                              </Badge>
                            </HStack>
                          </CardHeader>
                          <CardBody>
                            <VStack align="stretch" spacing={4}>
                              <Box>
                                <Text fontSize="xs" fontWeight="bold" color={mutedColor} mb={2} textTransform="uppercase">
                                  Key Findings
                                </Text>
                                {Array.isArray(data.key_findings) ? (
                                  <List spacing={2}>
                                    {data.key_findings.slice(0, 5).map((finding: any, i: number) => (
                                      <ListItem key={i} fontSize="sm" display="flex" alignItems="start">
                                        <ListIcon as={ChevronRightIcon} color="brand.500" mt={1} />
                                        <Text as="span">{typeof finding === 'string' ? finding : finding.finding}</Text>
                                      </ListItem>
                                    ))}
                                  </List>
                                ) : (
                                  <VStack align="stretch" spacing={2}>
                                    {Object.entries(data.key_findings).map(([key, value]) => (
                                      <Box key={key} p={2} bg="gray.50" borderRadius="md">
                                        <Text fontSize="xs" fontWeight="bold">{key}</Text>
                                        <Text fontSize="sm">{String(value)}</Text>
                                      </Box>
                                    ))}
                                  </VStack>
                                )}
                              </Box>

                              {data.recommendations && data.recommendations.length > 0 && (
                                <Box>
                                  <Divider my={2} />
                                  <Text fontSize="xs" fontWeight="bold" color={mutedColor} mb={2} textTransform="uppercase">
                                    Recommendations
                                  </Text>
                                  <List spacing={2}>
                                    {data.recommendations.slice(0, 3).map((rec: string, i: number) => (
                                      <ListItem key={i} fontSize="sm" color="gray.600" display="flex">
                                        <ListIcon as={CheckCircleIcon} color="green.500" mt={1} />
                                        {rec}
                                      </ListItem>
                                    ))}
                                  </List>
                                </Box>
                              )}

                              {data.raw_data && (
                                <Accordion allowToggle mt={4}>
                                  <AccordionItem border="none">
                                    <AccordionButton px={0} _hover={{ bg: 'transparent' }}>
                                      <Box flex="1" textAlign="left">
                                        <Text fontSize="xs" color="brand.500" fontWeight="bold">
                                          VIEW RAW DATA
                                        </Text>
                                      </Box>
                                      <AccordionIcon color="brand.500" />
                                    </AccordionButton>
                                    <AccordionPanel pb={4} px={0}>
                                      <Code
                                        display="block"
                                        whiteSpace="pre"
                                        p={2}
                                        borderRadius="md"
                                        fontSize="xs"
                                        overflowX="auto"
                                        maxH="200px"
                                      >
                                        {JSON.stringify(data.raw_data, null, 2)}
                                      </Code>
                                    </AccordionPanel>
                                  </AccordionItem>
                                </Accordion>
                              )}
                            </VStack>
                          </CardBody>
                        </Card>
                      );
                    })}
                  </SimpleGrid>

                  <Box pt={8} borderTopWidth="1px" w="full" textAlign="center">
                    <Text fontSize="sm" color={mutedColor}>
                      Analysis completed at: {new Date(results.timestamp).toLocaleString()}
                    </Text>
                  </Box>
                </VStack>
              )}
            </VStack>
          )}

          {/* Footer */}
          <Box pt={16} pb={8} textAlign="center">
            <Text fontSize="sm" color={mutedColor}>
              This system uses specialized AI agents to analyze FDA data. Results should be verified with official FDA sources.
            </Text>
          </Box>
        </VStack>
      </Container>
    </Box>
  );
}