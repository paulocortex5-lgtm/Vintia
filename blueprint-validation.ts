// Blueprint validation function based on Render API OpenAPI specification

interface ValidateBlueprintResponse {
  valid: boolean;
  errors?: {
    path: string;
    error: string;
    line: number;
    column: number;
  }[];
  plan?: {
    services: string[];
    databases: string[];
    keyValue: string[];
    envGroups: string[];
    workflows: string[];
    totalActions: number;
  };
}

interface ValidateBlueprintOptions {
  apiToken?: string;
}

/**
 * Validates a Render Blueprint (render.yaml) using the Render API
 * @param ownerId - The workspace ID to validate against
 * @param blueprintContent - The render.yaml content as string or Buffer
 * @param options - Optional configuration (apiToken for authentication)
 * @returns Promise resolving to validation result
 * @throws Error if validation fails or network error occurs
 */
export async function validateBlueprint(
  ownerId: string,
  blueprintContent: string | Buffer,
  options: ValidateBlueprintOptions = {}
): Promise<ValidateBlueprintResponse> {
  // Check if we're in a browser or Node.js environment
  const isNode = typeof process !== 'undefined' && process.versions?.node;
  
  let fetch: typeof globalThis.fetch;
  let FormData: typeof globalThis.FormData;
  
  if (isNode) {
    // In Node.js, we need to import these modules
    // Note: For Node.js <18, you may need to install node-fetch and form-data
    // and uncomment the following lines:
    // const { default: fetchNode } = await import('node-fetch');
    // const { default: FormDataNode } = await import('form-data');
    // fetch = fetchNode;
    // FormData = FormDataNode;
    
    // For Node.js 18+ with experimental fetch or using undici:
    fetch = globalThis.fetch;
    FormData = globalThis.FormData;
    
    if (!fetch || !FormData) {
      throw new Error(
        'fetch and FormData are not available. ' +
        'In Node.js <18, install node-fetch and form-data packages. ' +
        'In Node.js >=18, enable experimental fetch or use a polyfill.'
      );
    }
  } else {
    // Browser environment
    fetch = window.fetch;
    FormData = window.FormData;
  }

  // Create form data
  const form = new FormData();
  form.append('ownerId', ownerId);
  
  // Create file blob from content
  let fileBlob: Blob;
  if (typeof blueprintContent === 'string') {
    fileBlob = new Blob([blueprintContent], { type: 'application/yaml' });
  } else if (Buffer.isBuffer(blueprintContent)) {
    fileBlob = new Blob([blueprintContent], { type: 'application/yaml' });
  } else {
    throw new Error('blueprintContent must be a string or Buffer');
  }
  
  form.append('file', fileBlob, 'render.yaml');

  // Prepare headers
  const headers: HeadersInit = {};
  if (options.apiToken) {
    headers['Authorization'] = `Bearer ${options.apiToken}`;
  }

  // Make request to Render API
  const response = await fetch('https://api.render.com/v1/blueprints/validate', {
    method: 'POST',
    headers,
    body: form,
  });

  // Handle HTTP errors
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorData = await response.json();
      if (errorData.message) {
        errorMessage = errorData.message;
      }
    } catch (e) {
      // Ignore parsing errors
    }
    throw new Error(errorMessage);
  }

  // Parse and return response
  return response.json();
}

// Example usage:
// import { validateBlueprint } from './blueprint-validation';
//
// async function example() {
//   const ownerId = 'tea-cjnxpkdhshc73d12t9i0';
//   const blueprintContent = `
//   services:
//     - type: web
//       name: my-service
//       env: docker
//       plan: free
//       repo: https://github.com/your-repo/your-service
//       branch: main
//   `;
//   
//   try {
//     const result = await validateBlueprint(ownerId, blueprintContent, {
//       apiToken: process.env.RENDER_API_TOKEN // or your token
//     });
//     
//     if (result.valid) {
//       console.log('Blueprint is valid!');
//       console.log('Plan:', result.plan);
//     } else {
//       console.log('Blueprint validation failed:');
//       console.log(result.errors);
//     }
//   } catch (error) {
//     console.error('Validation error:', error.message);
//   }
// }
//
// example();