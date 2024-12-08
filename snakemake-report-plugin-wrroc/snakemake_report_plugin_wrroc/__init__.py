from dataclasses import dataclass, field
from typing import Optional

import snakemake
from snakemake.logging import logger
import os
from subprocess import run, CalledProcessError


from snakemake_interface_common.exceptions import WorkflowError  # noqa: F401
from snakemake_interface_report_plugins.reporter import ReporterBase
from snakemake_interface_report_plugins.settings import ReportSettingsBase

from rocrate.rocrate import ROCrate
from rocrate.model import ContextEntity, Person
import re

# Optional:
# Define additional settings for your reporter.
# They will occur in the Snakemake CLI as --report-<reporter-name>-<param-name>
# Omit this class if you don't need any.
# Make sure that all defined fields are Optional (or bool) and specify a default value
# of None (or False) or anything else that makes sense in your case.
@dataclass
class ReportSettings(ReportSettingsBase):
    """Additional settings for the RO-Crate reporter.
       They will occur in the Snakemake CLI as --report-wrroc-<param-name>
       Make sure that any further defined fields are Optional (or bool) and specify a default
       value of None (or False) or else Snakemake will demand these settings even when the
       reporter is not in use. Use the "required" flag below for required options.
    """
    exclude: Optional[str] = field(
        default=None,
        metadata={
            "help": "Comma-separated list of extra files to exclude",
            # Optionally request that setting is also available for specification
            # via an environment variable. The variable will be named automatically as
            # SNAKEMAKE_REPORT_<reporter-name>_<param-name>, all upper case.
            # This mechanism should ONLY be used for passwords and usernames.
            # For other items, we rather recommend to let people use a profile
            # for setting defaults
            # (https://snakemake.readthedocs.io/en/stable/executing/cli.html#profiles).
            "env_var": False,
            # Optionally specify a function that parses the value given by the user.
            # This is useful to create complex types from the user input.
            #"parse_func": ...,
            # If a parse_func is specified, you also have to specify an unparse_func
            # that converts the parsed value back to a string.
            #"unparse_func": ...,
            # Optionally specify that setting is required when the reporter is in use.
            "required": False,
        },
    )

    force: bool = field(
        default=False,
        metadata={
            "help": "Continue even if there are non-conformities",
            "env_var": False,
            "required": False,
        }
    )

    user_orcid: str = field(
        default=None,
        metadata={
            "help": "Workflow user ORCID",
            "env_var": False,
            "required": False,
        },
    )

    user_name: str = field(
        default=None,
        metadata={
            "help": "Workflow user name",
            "env_var": False,
            "required": False,
        },
    )

    user_email: str = field(
        default=None,
        metadata={
            "help": "Workflow user email",
            "env_var": False,
            "required": False,
        },
    )

    user_affiliation: str = field(
        default=None,
        metadata={
            "help": "Workflow user affiliation",
            "env_var": False,
            "required": False,
        },
    )



# Required:
# Implementation of your reporter
class Reporter(ReporterBase):
    def __post_init__(self, excludelist = (".snakemake", ".git", ".github", ".test", ".gitignore")):
        # initialize additional attributes
        # Do not overwrite the __init__ method as this is kept in control of the base
        # class in order to simplify the update process.
        # See https://github.com/snakemake/snakemake-interface-report-plugins/snakemake_interface_report_plugins/reporter.py # noqa: E501
        # for attributes of the base class.
        # In particular, the settings of above ReportSettings class are accessible via
        # self.settings.
        self.outdir = "ro-crate_out_copymetadata"
        self.excludelist = list(excludelist)
        self.excludelist.append(self.outdir)

        # Add user settings
        if self.settings.exclude:
            self.excludelist.extend(self.settings.exclude.split(','))
        self.conformance_force = self.settings.force
        
        # Create User Information
        self.user_id_order = ['ORCID', 'email', 'name']
        self.user_properties = ['name', 'affiliation', 'email']
        self.user = {}
        if self.settings.user_orcid and self.clean_orcid(): self.user['ORCID'] = self.clean_orcid()
        if self.settings.user_name: self.user['name'] = self.settings.user_name
        if self.settings.user_email: self.user['email'] = self.settings.user_email
        if self.settings.user_affiliation: self.user['affiliation'] = self.settings.user_affiliation

        # Load the existing Workflow RO-Crate
        try:
            self.old_crate = ROCrate(source='./', exclude=self.excludelist)
        except ValueError:
            self.old_crate = None

        # Create a new crate for output
        self.crate = ROCrate(exclude=self.excludelist)

    def clean_orcid(self):
        """
        Ensure that any provided ORCID follows correct format.
        Either:
        0000-0000-0000-0000
        or:
        https://orcid.org/0000-0000-0000-0000
        """
        orcid = self.settings.user_orcid

        web_pattern = re.compile(r'https://orcid.org/')
        orcid_pattern = re.compile(r'\d\d\d\d-\d\d\d\d-\d\d\d\d-\d\d\d\d')

        if web_pattern.search(orcid) and orcid_pattern.search(orcid) and \
            web_pattern.search(orcid).span() == (0, 18) and orcid_pattern.search(orcid).span() == (18, 37):
            return(orcid)
        elif orcid_pattern.match(orcid):
            return(f'https://orcid.org/{orcid}')
        else:
            logger.warning(f"{orcid} is not a valid ORCID identity")
            return(None)

    def check_essential_files(self):
        """Check for the presence of essential files.

           We want to scan/report everything even if there is an error.

           See https://docs.google.com/document/d/1KozjchVFqrctBGooRR-OWpifyI0TRuoSWIUUGIDWNyI/edit?tab=t.0
        """
        errors = []

        # A license
        if not os.path.exists("LICENSE.md") or not os.path.exists("LICENSE.txt"):
            errors.append("No LICENSE.md or LICENSE.txt found.")

        # TODO - do we need CODE_OF_CONDUCT.md and CONTRIBUTING.md too? I'm making these
        # warnings just now.

        # TODO - do we need the remote URL for a Workflow Run Crate? Or is this only a
        # nice to have? I've moved this check to warnings for now.

        # We need a README.md
        if not os.path.exists("README.md"):
            errors.append("Add a README.md file to introduce your workflow.")

        # The main workflow should be called "workflow/Snakefile"
        main_snakefile = os.path.relpath(self.dag.workflow.main_snakefile)
        if main_snakefile != "workflow/Snakefile":
            # FIXME - this is returning nonsense in Snakemake 8. Does the regular html
            # reporter get a meaningful value? Nope.
            errors.append("Your main Snakefile needs to be called 'workflow/Snakefile'."
                          f" Please rename {main_snakefile}.")

        # And we want a config.yaml file.
        if not os.path.exists("config/config.yaml"):
            if os.path.exists("config/config.json"):
                # For anything that needs to be hand-edited and not read by JS, YAML >> JSON.
                errors.append("Please convert your config/config.json file to YAML format using"
                              " <insert suggested converter tool here>.")
            else:
                errors.append("Please supply a default/sample configuration file for the workflow"
                              " under 'config/config.yaml'.")

        # GitHub wants a "CITATION.cff"
        # It looks like we should be able to pull the info from this into the metadata -
        # see https://www.researchobject.org/ro-crate/specification/1.1/contextual-entities.html#publications-via-citation-property
        # but I'm not sure how useful this is or where that code would live. Given that the
        # cffconvert tool (and library) already supports CFF to schema.org conversion I'd imagine
        # this is already done in other tools.
        if not os.path.exists("CITATION.cff"):
            errors.append("You must include a 'CITATION.cff' file. If you are not requesting a"
                          " specific citation for use of the workflow, please <link instrux here"
                          " for making a minimal CFF, or maybe create a template>")

        return errors

    def check_desirable_files(self):
        """Things that *should* be in the submission but are not essential.
        """
        errors = []

        # Evidence of Git repo. This is probably not the best way to check but we'd like to know
        # the remote URL
        if not os.path.exists(".git/config"):
            if os.path.exists("../.git/config"):
                # We are within a GIT repo but not at the top level, so:
                if not os.path.exists("workflowhub.yml"):
                    errors.append("Since your workflow is in a subdirectory of your GIT repo,"
                                  " you must include a 'workflowhub.yml' file.")
            else:
                errors.append("No .git/config file found. Is the code under source control?")

        # WorkflowHub says the tests should be under "tests" but Snakemake says they should
        # be under ".tests". Can we be opinionated about it?
        if not os.path.isdir("tests"):
            if os.path.isdir(".tests"):
                errors.append("You have a '.tests' directory. Please rename it as 'tests' or else"
                              " make a symlink called 'tests'.")
            else:
                errors.append("Please add a 'tests' directory with 'unit' and 'integration'"
                              " subdirectories.")
        elif not(os.path.isdir("tests/integration") and os.path.isdir("tests/unit")):
            errors.append("Please create 'unit' and 'integration' subdirectories under 'tests'.")


        if not(os.path.exists("CODE_OF_CONDUCT.md") and os.path.exists("CONTRIBUTING.md")):
            errors.append("Please add CODE_OF_CONDUCT.md and CONTRIBUTING.md files."
                          " You may be happy copying the versions from <suggest something here>")

        return errors

    def conformance_check(self):
        """Ensure that some expected files are found. The rocrate module does
           not scan the files until the crate is exported, so we have to look for the
           files here.
        """
        essential_problems = self.check_essential_files()
        if essential_problems:
            for prob in essential_problems:
                logger.error(f"Conformance error: {prob}")
            msg = f"Exiting due to {len(essential_problems)} conformance issues."
            if self.conformance_force:
                logger.warning(f"Continuing despite {len(essential_problems)} conformance issues.")
            else:
                raise RuntimeError(f"Exiting due to {len(essential_problems)} conformance issues.")

        desirable_problems = self.check_desirable_files()
        if desirable_problems:
            for prob in desirable_problems:
                logger.warning(f"Conformance warning: {prob}")
            logger.warning(f"Continuing despite len(desirable_problems) warnings.")

    def create_rulegraph(self):
        # images/rulegraph.svg should be something we can auto-generate. self.dag has methods dot()
        # and rule_dot() which can make the graph for us, but it still needs converting to SVG.
        # TODO: Replace hardcoded file paths with path provided to function
        #       (this will need to match the path given to the RO-Crate generator too)

        if os.path.exists("image/rulegraph.svg"):
                return True

        else:
            logger.warning("Auto generating 'image/rulegraph.svg'")
            try:
                os.makedirs("image", exist_ok=True)
                with open("image/rulegraph.dot", "x") as dotfh:
                    print(self.dag.rule_dot(), file=dotfh)
            except FileExistsError:
                # Never mind, use the one we have. Maybe the user edited it.
                logger.info("Using existing 'image/rulegraph.dot'")

            # For converting .dot to .svg I don't see a better way than calling the graphviz
            # program directly.
            try:
                run(['dot', '-Tsvg', 'image/rulegraph.dot', '-o', 'image/rulegraph.svg'],
                     check = True,
                     capture_output = True,
                     text = True)
            except CalledProcessError as e:
                logger.error(str(e.stderr).rstrip())
                logger.error("The 'dot' program returned the above error attempting to convert the rulegraph.")
                return False
            except FileNotFoundError as e:
                logger.error(str(e))
                logger.error("The 'dot' program was not found. Unable to auto-convert the rulegraph.")
                return False
            else:
                return True

    def copy_old_crate_data(self):
        """
        This copies the metadata from the original Workflow RO-Crate to make
        the basis of the new Workflow Run RO-Crate.
        """
        crate = self.crate
        old_crate = self.old_crate

        # copy across files and data structure.
        # NOTE: we have to use the add_dataset and add_file commands,
        #       *not* the plain add command (as for the contextual entity),
        #       or the library will not load the files contained within
        #       the dataset directories.
        for entity in old_crate.data_entities:
            if 'Dataset' in entity.type:
                crate.add_dataset(source=entity.id, dest_path=entity.id, 
                                       properties=entity.properties())
            elif 'File' in entity.type:
                crate.add_file(source=entity.id, dest_path=entity.id,
                                    properties=entity.properties())

            if entity.id == old_crate.mainEntity:
                crate.mainEntity = entity
        
        # copy desired metadata from old crate
        for entity in old_crate.contextual_entities:
            crate.add(entity)

        # copy existing metadata
        if old_crate.mainEntity:
            crate.mainEntity = old_crate.mainEntity
        if old_crate.license:
            crate.license = old_crate.license
        if old_crate.isBasedOn:
            crate.isBasedOn = old_crate.isBasedOn
        if old_crate.name:
            crate.name = old_crate.name

    def create_base_crate_from_scratch(self):
        """
        Function for creating the base Workflow Run RO-Crate from scratch.
        """
        raise RuntimeError(f"Exiting because we cannot yet create an RO-Crate from scratch")

    def create_user_entry(self):
        """
        Create user entry for RO-Crate, using wrroc executor inputs
        """
        id_order = self.user_id_order
        user_properties = self.user_properties
        crate = self.crate

        person_properties = {}
        person_properties['@id'] = 'ANONYMOUS'
        person_properties['name'] = 'ANONYMOUS'
        for id_string in id_order:
            if id_string in self.user:
                person_properties["@id"] = self.user[id_string]
                break

        for user_string in user_properties:
            if user_string in self.user: person_properties[user_string] = self.user[user_string]

        agent = crate.add(Person(crate,
                                identifier=person_properties["@id"],
                                properties=person_properties))

        return(agent)

    def render(self):
        try:
            self.try_render()
        except Exception as e:
            # Catch all exceptions and turn them into error messages.
            logger.error(e)

    def try_render(self):
        """Generate the crate, using the ROCrate library.
        """
        logger.info(f"Excludelist: {self.excludelist}")

        self.conformance_check()

        # Copy information from the original Workflow RO-Crate, if it exists
        # TODO: Otherwise create the base of our Workflow Run RO-Crate from scratch
        if self.old_crate:
            self.copy_old_crate_data()
        else:
            self.create_base_crate_from_scratch()

        crate = self.crate

        # check that a workflow diagram is listed,
        # if not we will check for it at 'image/rulegraph.svg',
        # creating it if it does not already exist
        if 'image' not in crate.mainEntity.properties() and self.create_rulegraph():
            graph = crate.add_file(source='image/rulegraph.svg', dest_path='image/rulegraph.svg',
                               properties={'@type':['File','ImageObject']})
            crate.mainEntity.append_to('image',graph)


        # Provenance Crate - add snakemake version
        for entity in crate.contextual_entities:
            if entity.type == 'ComputerLanguage' and 'snakemake' in entity.id.lower():
                entity['version'] = snakemake.__version__.split("+")[0]
        
        # Provenance Crate - record execution of workflow as a CreateAction object
        workflow_run_properties = {
            "@id":"FIXME-add-workflow-run-properties-id",
            "@type":"CreateAction",
            "name":"Snakemake workflow run (FIXME)",
            "endTime":"FIXME date",
            #"subjectOf":{"@id":"FIXME creative work (workflow?)"},
            "object":["FIXME inputs"],
            "result":["FIXME outputs"]
        }
        instruments = {}
        for entity in crate.data_entities:
            if 'ComputationalWorkflow' in entity.type:
                instruments["@id"] = entity.id
        if '@id' in instruments:
            workflow_run_properties['instruments'] = instruments
        workflow_run = crate.add(
            ContextEntity(crate, identifier=workflow_run_properties["@id"],
                          properties=workflow_run_properties)
        )
        logger.info(workflow_run_properties)

        # Provenance Run Crate (individual step information)

        # print basic information (start/end) of each job
        for rulename, rule  in self.rules.items():
            print(f"rule: {rulename}")
            #print(rule)
            #print("rule: " + rec.rule)
            #print("starttime: " + str(rec.starttime))
            #print("endtime: " + str(rec.endtime))
            #print("ROCrate date published: " + str(self.crate.datePublished.date()))

        # Add Person running workflow (agent)
        workflow_run.append_to( "agent", [self.create_user_entry()] )
        
        
        # Reference CreateAction in the root Dataset
        crate.root_dataset.append_to(
            "mentions" , [{"@id": workflow_run.id}]
        )
        
        # Set the conformsTo statement for the root Dataset.
        # Note that this will replace any pre-existing conformsTo information
        self.crate.root_dataset["conformsTo"] = [
                    {"@id": "https://w3id.org/ro/wfrun/process/0.1"},
                    {"@id": "https://w3id.org/ro/wfrun/workflow/0.5"},
                    {"@id": "https://w3id.org/workflowhub/workflow-ro-crate/1.0"}
                ]


        crate.write(self.outdir)
        crate.write_zip(self.outdir + ".zip")

